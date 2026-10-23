"""WP5: every reader of athlete_season_stats must filter TOT + regular grain.

Greps the repo for SQL string literals that touch ``athlete_season_stats`` and
fails when a read query lacks a ``team_id`` filter. Migrations / DDL / writers
are allowlisted.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

ALLOWLIST_PATH_PARTS = (
    "migrations/",
    "gravity_api/tests/test_ass_readers_filter_grain.py",
    "gravity_api/services/sport_pipeline/season_stats.py",  # writer
    "gravity_api/services/sport_pipeline/season_stats_store.py",  # writer + load API
    "gravity_api/jobs/backfill_season_stats.py",
    "gravity_api/jobs/backfill_career_stats.py",
    "gravity_api/scrapers/clients/espn_season_history.py",
    "gravity_api/scrapers/parsers/stat_catalog.py",
    "docs/",
    "reports/",
)

_WRITE_OR_DDL = re.compile(
    r"\b(INSERT\s+INTO|UPDATE\s+|DELETE\s+FROM|CREATE\s+TABLE|ALTER\s+TABLE|"
    r"DROP\s+TABLE|CREATE\s+(UNIQUE\s+)?INDEX|CREATE\s+OR\s+REPLACE\s+VIEW|"
    r"REFERENCES|ON\s+CONFLICT)\b",
    re.IGNORECASE,
)

_TABLE_RE = re.compile(r"\bathlete_season_stats\b")
_EAV_RE = re.compile(r"\bathlete_season_stats_eav\b")
_FROM_JOIN = re.compile(
    r"\b(?:FROM|JOIN)\s+athlete_season_stats\b",
    re.IGNORECASE,
)


def _is_allowlisted(path: Path) -> bool:
    rel = path.relative_to(REPO_ROOT).as_posix()
    return any(part in rel for part in ALLOWLIST_PATH_PARTS)


def _iter_source_files() -> list[Path]:
    out: list[Path] = []
    for pattern in ("**/*.py", "**/*.sql"):
        for path in REPO_ROOT.glob(pattern):
            if any(
                part in path.parts
                for part in (".git", ".venv", "venv", "node_modules", "__pycache__")
            ):
                continue
            out.append(path)
    return out


def _has_team_id_filter(snippet: str) -> bool:
    return bool(
        re.search(r"team_id\s*=\s*'TOT'", snippet)
        or re.search(r"\bteam_id\s*=", snippet)
        or re.search(r"AND\s+team_id\b", snippet, re.I)
    )


def _python_string_literals(path: Path) -> list[str]:
    """Extract constant string literals from a Python file (incl. joined SQL)."""
    src = path.read_text(encoding="utf-8", errors="replace")
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return [src] if _TABLE_RE.search(src) else []

    out: list[str] = []

    class Visitor(ast.NodeVisitor):
        def visit_Constant(self, node: ast.Constant) -> None:
            if isinstance(node.value, str) and _TABLE_RE.search(node.value):
                out.append(node.value)
            self.generic_visit(node)

        def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
            # Rebuild f-string SQL with placeholders for expressions.
            parts: list[str] = []
            for v in node.values:
                if isinstance(v, ast.Constant) and isinstance(v.value, str):
                    parts.append(v.value)
                else:
                    parts.append(" _ ")
            joined = "".join(parts)
            if _TABLE_RE.search(joined):
                out.append(joined)
            self.generic_visit(node)

    Visitor().visit(tree)
    return out


def test_ass_readers_filter_grain():
    offenders: list[str] = []
    for path in _iter_source_files():
        if _is_allowlisted(path):
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()

        if path.suffix == ".sql":
            text = path.read_text(encoding="utf-8", errors="replace")
            snippets = [text] if _FROM_JOIN.search(text) else []
        else:
            snippets = _python_string_literals(path)

        for snippet in snippets:
            # Require SELECT so docstring prose ("from athlete_season_stats") is ignored.
            if not re.search(r"\bSELECT\b", snippet, re.I):
                continue
            if not _FROM_JOIN.search(snippet):
                continue
            if _WRITE_OR_DDL.search(snippet):
                continue
            if not _has_team_id_filter(snippet):
                preview = " ".join(snippet.split())[:220]
                offenders.append(f"{rel}: {preview}")

    assert not offenders, (
        "Reader SQL on athlete_season_stats missing team_id filter:\n"
        + "\n".join(offenders)
    )


def test_no_primary_reads_of_athlete_season_stats_eav():
    """Cohort / raw readers must not prefer the PR #17 ``_eav`` rename."""
    banned_dirs = (
        REPO_ROOT / "gravity_api" / "services",
        REPO_ROOT / "gravity_api" / "jobs",
        REPO_ROOT / "scripts",
    )
    offenders: list[str] = []
    for base in banned_dirs:
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            if _EAV_RE.search(text):
                offenders.append(path.relative_to(REPO_ROOT).as_posix())
    assert not offenders, (
        "athlete_season_stats_eav still referenced (use athlete_season_stats + grain): "
        + ", ".join(offenders)
    )
