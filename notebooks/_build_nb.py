"""Generator for gravity_exports_eda_train_by_sport.ipynb (rebuilt with fixes)."""
import json
from pathlib import Path


def md(text):
    return {"cell_type": "markdown", "metadata": {}, "source": [l + "\n" for l in text.strip("\n").split("\n")]}


def code(text):
    return {"cell_type": "code", "metadata": {}, "source": [l + "\n" for l in text.strip("\n").split("\n")],
            "outputs": [], "execution_count": None}


cells = []

cells.append(md("""# Gravity Raw Exports — EDA, Clean, Augment & Train (By Sport)

Per-sport pipeline for raw athlete CSV exports:
- **EDA** — missingness, conference audit, target & stat coverage, plots
- **Clean** — fix conference (standing → league), safe numeric coercion, outliers
- **Impute** — hierarchical imputation with observation masks
- **Augment** — bootstrap, missingness sim, cohort jitter, school swap (CFB)
- **Train** — sklearn GradientBoostingRegressor (value + quality), leakage-guarded
- **Export** — production-style bundle artifacts per sport

**Order matters:** JSON is flattened *before* cleaning so `raw_data_json` stats survive.

Expected files (upload to Colab or set `DATA_DIR`):
`athletes_cfb_raw.csv`, `athletes_nfl_raw.csv`, `athletes_ncaab_mens_raw.csv`,
`athletes_ncaab_womens_raw.csv`, `athletes_wnba_raw.csv`"""))

cells.append(code("""#@title 0.1 Install dependencies
!pip -q install pandas numpy scikit-learn matplotlib seaborn joblib"""))

cells.append(code('''#@title 0.2 Configuration
from __future__ import annotations

import json
import math
import pickle
import re
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

# --- paths (edit for Colab / local) ---
# Colab after upload: DATA_DIR = Path("/content")
DATA_DIR = Path("data/gravity_exports/raw")
if not DATA_DIR.exists():
    _fallback = Path.home() / "Downloads/gravity_exports/raw"
    if _fallback.exists():
        DATA_DIR = _fallback

ARTIFACT_DIR = Path("artifacts")
EXPORT_MODELS = True
RANDOM_SEED = 42
RUN_SPORTS = ["cfb", "nfl", "ncaab_mens", "ncaab_womens", "wnba"]  # subset e.g. ["cfb"]

SPORT_CONFIG = {
    "cfb": {
        "file": "athletes_cfb_raw.csv", "league": "ncaa", "conference_parse": "college",
        "train_objectives": ["value_nil", "value_proxy_ig", "quality", "quality_external"],
        "export_objectives": ["value_nil"],
        "blocked_export_objectives": ["quality", "value_proxy_ig"],
        "min_rows_train": 80,
    },
    "nfl": {
        "file": "athletes_nfl_raw.csv", "league": "pro", "conference_parse": "division",
        "train_objectives": ["quality"], "export_objectives": [], "min_rows_train": 100,
    },
    "ncaab_mens": {
        "file": "athletes_ncaab_mens_raw.csv", "league": "ncaa", "conference_parse": "college",
        "train_objectives": ["quality"], "export_objectives": [], "min_rows_train": 80,
    },
    "ncaab_womens": {
        "file": "athletes_ncaab_womens_raw.csv", "league": "ncaa", "conference_parse": "college",
        "train_objectives": ["quality"], "export_objectives": [], "min_rows_train": 60,
    },
    "wnba": {
        "file": "athletes_wnba_raw.csv", "league": "pro", "conference_parse": "division",
        "train_objectives": ["quality"], "export_objectives": [], "min_rows_train": 40,
    },
}

AUG_FLAGS = {
    "cfb": {"bootstrap_multiplier": 2.0, "missingness_p": 0.35, "jitter_sigma": 0.05, "school_swap_p": 0.10},
    "nfl": {"bootstrap_multiplier": 1.5, "missingness_p": 0.25, "jitter_sigma": 0.04, "school_swap_p": 0.0},
    "ncaab_mens": {"bootstrap_multiplier": 2.0, "missingness_p": 0.20, "jitter_sigma": 0.05, "school_swap_p": 0.05},
    "ncaab_womens": {"bootstrap_multiplier": 3.0, "missingness_p": 0.20, "jitter_sigma": 0.04, "school_swap_p": 0.05},
    "wnba": {"bootstrap_multiplier": 5.0, "missingness_p": 0.15, "jitter_sigma": 0.03, "school_swap_p": 0.0},
}

P5_CONFERENCES = {"SEC", "Big Ten", "Big 12", "ACC", "Pac-12", "Pac-12 Conference"}

np.random.seed(RANDOM_SEED)
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
print("DATA_DIR:", DATA_DIR.resolve())
print("RUN_SPORTS:", RUN_SPORTS)'''))

cells.append(code('''#@title 0.3 Optional: upload CSVs (Colab)
try:
    from google.colab import files
    uploaded = files.upload()  # upload all athletes_*_raw.csv files
    DATA_DIR = Path("/content")
    print("Uploaded to", DATA_DIR, "files:", list(uploaded.keys()))
except ImportError:
    print("Not in Colab — using DATA_DIR from config")'''))

UTILS = r'''#@title 0.4 Shared utilities (load, clean, impute, augment, train, EDA)

import matplotlib
matplotlib.use("Agg") if False else None  # keep default; Colab renders inline
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import GradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error

# Columns never used as model features (identity / leakage / bookkeeping)
META_COLS = {
    "entity_id", "entity_type", "sport", "name", "school", "position",
    "conference_standing", "conference", "division", "class_year", "scraped_at",
    "scrape_version", "has_raw_scrape", "raw_data_json", "source_file",
    "conference_imputed_from", "school_clean", "team_clean", "is_augmented",
    "aug_type", "parent_entity_id", "sample_weight", "is_active", "roster_status",
    "target_log_nil_usd", "target_log_ig", "target_quality", "proof_proxy",
    "hometown", "home_state", "espn_id", "jersey_number",
}

# raw_ / text columns that must NOT be coerced to numeric (JSON blobs, names, ids)
NON_NUMERIC_RAW = {
    "raw_data_json", "raw_raw", "raw_season_stats", "raw_achievements_json",
    "raw_national_awards_json", "raw_conference_honors_json", "raw_award_names",
    "raw_controversy_signals", "raw_team", "raw_college", "raw_player_name",
    "raw_position", "raw_handle_source", "raw_stats_source", "raw_stats_as_of",
    "raw_headshot_url", "raw_current_injury_status", "raw_collection_timestamp",
    "raw_collection_errors", "raw_external_id_espn", "raw_sport", "raw_conference",
    "raw_scrape_version", "raw_injury_type_l2y",
}

NUMERIC_EXTRA = {
    "nil_valuation", "news_count_30d", "data_quality_score", "height_inches",
    "weight_lbs", "nil_environment_score", "conference_media_index",
}

POSITION_GROUPS_CFB = {
    "QB": "QB", "RB": "RB", "FB": "RB", "TB": "RB", "WR": "WR", "TE": "TE",
    "OL": "OL", "OT": "OL", "OG": "OL", "C": "OL", "G": "OL", "T": "OL",
    "DL": "DL", "DE": "DL", "DT": "DL", "NT": "DL", "EDGE": "DL",
    "LB": "LB", "ILB": "LB", "OLB": "LB", "MLB": "LB",
    "DB": "DB", "CB": "DB", "S": "DB", "SAF": "DB", "FS": "DB", "SS": "DB",
    "PK": "ST", "K": "ST", "P": "ST", "LS": "ST",
}

CFB_STAT_COLS = [
    "raw_cfb_passing_yards", "raw_cfb_passing_tds", "raw_cfb_passer_rating",
    "raw_cfb_rushing_yards", "raw_cfb_rushing_tds", "raw_cfb_rush_attempts",
    "raw_cfb_receiving_yards", "raw_cfb_receptions", "raw_cfb_receiving_tds",
    "raw_cfb_sacks", "raw_cfb_ints_def", "raw_cfb_tackles", "raw_cfb_games_played",
]

SOCIAL_COLS = ["instagram_followers", "twitter_followers", "tiktok_followers", "nil_valuation"]

# Per-objective leakage exclusions: substrings matched (case-insensitive) against EVERY
# column name. Raw scrapes duplicate the label under many aliases (raw_nil_valuation,
# json_nil_valuation, raw_instagram_followers_conf, ...), so we match by token, not exact
# name, to avoid target leakage. Note: nil_environment_score / team_nil_collective are
# market-context features (kept); nil_valuation / nil_deal are the label (dropped).
LEAK_PATTERNS = {
    "value_nil": ["nil_valuation", "nil_deal", "log1p_nil"],
    "value_proxy_ig": ["instagram", "log1p_instagram"],
    "quality": ["instagram", "twitter", "tiktok", "follower",
                "nil_valuation", "nil_deal", "log1p_nil", "log1p_instagram", "log1p_twitter",
                "proof_proxy", "external_quality"],
    "quality_external": ["external_quality", "all_american", "national_awards", "conference_honors",
                         "heisman", "draft_round", "achievements_json"],
}


def _leaked_columns(columns, objective):
    pats = LEAK_PATTERNS.get(objective, [])
    return {c for c in columns if any(p in c.lower() for p in pats)}

CLASS_YEAR_MAP = {
    "Freshman": 1, "Sophomore": 2, "Junior": 3, "Senior": 4, "Graduate": 5,
    "Redshirt Freshman": 1, "Redshirt Sophomore": 2, "Redshirt Junior": 3, "Redshirt Senior": 4,
}


def load_sport(sport_key: str, cfg: dict) -> pd.DataFrame:
    path = DATA_DIR / cfg["file"]
    if not path.exists():
        raise FileNotFoundError(f"Missing {path} — upload CSV or fix DATA_DIR")
    df = pd.read_csv(path, low_memory=False)
    df["sport"] = sport_key
    df["source_file"] = cfg["file"]
    return df


def parse_standing_to_league(val):
    if pd.isna(val):
        return np.nan
    s = str(val).strip()
    m = re.search(r"\bin\s+(.+)$", s, re.I)
    return m.group(1).strip() if m else s


def flatten_raw_json(df: pd.DataFrame) -> pd.DataFrame:
    """Parse raw_data_json -> json_* scalars and json_stat_* from season_stats.
    Must run BEFORE clean_dataframe so the JSON string is still intact."""
    rows = []
    series = df["raw_data_json"] if "raw_data_json" in df.columns else pd.Series([None] * len(df))
    for val in series:
        out = {}
        try:
            d = json.loads(val) if isinstance(val, str) else {}
        except (json.JSONDecodeError, TypeError, ValueError):
            rows.append(out)
            continue
        if not isinstance(d, dict):
            rows.append(out)
            continue
        for k, v in d.items():
            if isinstance(v, bool):
                out[f"json_{k}"] = float(v)
            elif isinstance(v, (int, float)) and k != "raw":
                out[f"json_{k}"] = v
        ss = d.get("season_stats")
        if isinstance(ss, dict):
            for k, v in ss.items():
                if isinstance(v, bool):
                    out[f"json_stat_{k}"] = float(v)
                elif isinstance(v, (int, float)):
                    out[f"json_stat_{k}"] = v
        rows.append(out)
    extra = pd.DataFrame(rows, index=df.index)
    # keep json_stat_* columns that have a useful amount of signal
    keep = [c for c in extra.columns if extra[c].notna().sum() >= max(20, 0.05 * len(df))]
    extra = extra[keep]
    return pd.concat([df, extra], axis=1)


def build_school_conference_map(df: pd.DataFrame) -> dict:
    tmp = df.copy()
    if "raw_conference" in tmp.columns:
        known = tmp.dropna(subset=["school"]).copy()
        known["conf_hint"] = known["raw_conference"]
        miss = known["conf_hint"].isna()
        if "conference" in known.columns:
            known.loc[miss, "conf_hint"] = known.loc[miss, "conference"].map(parse_standing_to_league)
        known = known[known["conf_hint"].notna() & (known["conf_hint"].astype(str) != "Unknown")]
        if len(known):
            return known.groupby("school")["conf_hint"].agg(lambda s: s.mode().iloc[0]).to_dict()
    if "conference" in tmp.columns:
        tmp["conf_hint"] = tmp["conference"].map(parse_standing_to_league)
        return tmp.groupby("school")["conf_hint"].agg(lambda s: s.mode().iloc[0]).to_dict()
    return {}


def _safe_numeric_coerce(out: pd.DataFrame, col: str) -> None:
    """Coerce only if it doesn't wipe out most existing values (protects text cols)."""
    base = out[col].notna().sum()
    coerced = pd.to_numeric(out[col], errors="coerce")
    if base == 0 or coerced.notna().sum() >= 0.5 * base:
        out[col] = coerced


def clean_dataframe(df: pd.DataFrame, sport_key: str, cfg: dict) -> pd.DataFrame:
    out = df.copy()
    if "conference" in out.columns:
        out["conference_standing"] = out["conference"]
    school_map = build_school_conference_map(out)

    def _conf_row(row):
        if pd.notna(row.get("raw_conference")):
            return row["raw_conference"], "raw_conference"
        parsed = parse_standing_to_league(row.get("conference_standing") or row.get("conference"))
        if pd.notna(parsed) and parsed != "Unknown":
            return parsed, "parsed_standing"
        sch = row.get("school")
        if sch in school_map:
            return school_map[sch], "school_map"
        return np.nan, "missing"

    if cfg["conference_parse"] == "division":
        src = out.get("conference_standing", out.get("conference", pd.Series(dtype=object)))
        out["division"] = src.map(parse_standing_to_league)
        out["conference"] = np.nan
        out["conference_imputed_from"] = "division_field"
    else:
        conf_vals = out.apply(_conf_row, axis=1, result_type="expand")
        out["conference"] = conf_vals[0]
        out["conference_imputed_from"] = conf_vals[1]

    out["school_clean"] = out["school"].astype(str).str.strip()
    out["team_clean"] = out["raw_team"].fillna(out["school_clean"]) if "raw_team" in out.columns else out["school_clean"]
    out["is_p5"] = out["conference"].isin(P5_CONFERENCES).astype(float) if "conference" in out.columns else 0.0

    for c in list(out.columns):
        if c in NON_NUMERIC_RAW or c.startswith("json_"):
            continue
        if c.startswith("raw_") or c.endswith("_followers") or c in NUMERIC_EXTRA:
            _safe_numeric_coerce(out, c)

    if "nil_valuation" in out.columns:
        out["nil_valuation_raw"] = out["nil_valuation"]
        if out["nil_valuation"].notna().any():
            cap = out["nil_valuation"].quantile(0.995)
            if pd.notna(cap) and cap > 0:
                out["nil_valuation"] = out["nil_valuation"].clip(upper=cap)

    if "is_active" in out.columns:
        active = out["is_active"].astype(str).str.lower().isin(["true", "1", "yes"]) | (out["is_active"] == True)
        out = out[active].copy()

    if "class_year" in out.columns:
        out["class_year_ord"] = pd.to_numeric(out["class_year"].map(CLASS_YEAR_MAP), errors="coerce")

    if sport_key == "cfb" and "position" in out.columns:
        out["position_group"] = out["position"].map(POSITION_GROUPS_CFB).fillna("OTHER")

    return out.reset_index(drop=True)


def impute_with_mask(df: pd.DataFrame, col: str, group_cols: list) -> pd.DataFrame:
    out = df
    obs = f"{col}_observed"
    out[obs] = out[col].notna().astype(float)
    group_cols = [c for c in group_cols if c in out.columns]
    med = out.groupby(group_cols)[col].transform("median") if group_cols else pd.Series(np.nan, index=out.index)
    out[col] = out[col].fillna(med).fillna(out[col].median())
    return out


def apply_imputation(df: pd.DataFrame, sport_key: str) -> pd.DataFrame:
    out = df.copy()
    id_groups = ["sport"]
    if "position" in out.columns:
        id_groups.append("position")
    if "position_group" in out.columns:
        id_groups.append("position_group")

    for col in ["height_inches", "weight_lbs", "class_year_ord"]:
        if col in out.columns:
            out = impute_with_mask(out, col, id_groups)
    for col in SOCIAL_COLS:
        if col in out.columns:
            out = impute_with_mask(out, col, id_groups + (["conference"] if "conference" in out.columns else []))
    for col in ["news_count_30d", "data_quality_score", "nil_environment_score", "conference_media_index"]:
        if col in out.columns:
            out = impute_with_mask(out, col, ["sport"])
    for col in CFB_STAT_COLS:
        if col in out.columns:
            out = impute_with_mask(out, col, id_groups)
    for col in [c for c in out.columns if c.startswith("json_stat_")]:
        out = impute_with_mask(out, col, id_groups)
    return out


def extract_features(df: pd.DataFrame, sport_key: str) -> pd.DataFrame:
    out = df.copy()
    if "instagram_followers" in out.columns:
        out["log1p_instagram"] = np.log1p(out["instagram_followers"].clip(lower=0))
    if "twitter_followers" in out.columns:
        out["log1p_twitter"] = np.log1p(out["twitter_followers"].clip(lower=0))
    if "news_count_30d" in out.columns:
        out["log1p_news"] = np.log1p(out["news_count_30d"].clip(lower=0))
    if "nil_valuation" in out.columns:
        out["log1p_nil"] = np.log1p(out["nil_valuation"].clip(lower=0))

    stat_cols = [c for c in CFB_STAT_COLS if c in out.columns]
    stat_cols += [c for c in out.columns if c.startswith("json_stat_")]
    stat_cols = list(dict.fromkeys(stat_cols))
    if stat_cols:
        stat_mat = out[stat_cols].apply(pd.to_numeric, errors="coerce")
        obs = stat_mat.notna().astype(float)
        filled = stat_mat.fillna(stat_mat.median(numeric_only=True))
        std = filled.std().replace(0, 1)
        z = (filled - filled.mean()) / std
        denom = obs.sum(axis=1).replace(0, np.nan)
        out["proof_proxy"] = (z * obs).sum(axis=1) / denom
        out["proof_proxy"] = out["proof_proxy"].fillna(out["proof_proxy"].median())

    # IMPORTANT: value targets must use ONLY originally-observed labels, not imputed
    # medians. apply_imputation() already filled nil_valuation/instagram_followers, so we
    # gate on the *_observed mask to recover the real labels.
    if "nil_valuation" in out.columns:
        obs = out["nil_valuation_observed"] if "nil_valuation_observed" in out.columns else pd.Series(1.0, index=out.index)
        real = (obs == 1.0) & (out["nil_valuation"] > 0)
        out["target_log_nil_usd"] = np.where(real, np.log1p(out["nil_valuation"]), np.nan)
    if "instagram_followers" in out.columns:
        obs_ig = out["instagram_followers_observed"] if "instagram_followers_observed" in out.columns else pd.Series(1.0, index=out.index)
        ig = pd.to_numeric(out["instagram_followers"], errors="coerce")
        real_ig = (obs_ig == 1.0) & (ig > 0) & (ig != 2500)
        out["target_log_ig"] = np.where(real_ig, np.log1p(ig.clip(lower=0)), np.nan)
    if "proof_proxy" in out.columns:
        out["target_quality"] = out["proof_proxy"]
    if "external_quality_score" in out.columns:
        obs_q = out["external_quality_score_observed"] if "external_quality_score_observed" in out.columns else pd.Series(np.nan, index=out.index)
        q = pd.to_numeric(out["external_quality_score"], errors="coerce")
        real_q = (obs_q == 1.0) & q.notna() & (q > 0)
        out["target_quality_external"] = np.where(real_q, q, np.nan)
    return out


def augment_bootstrap(df, n_mult, weight, rng):
    if n_mult <= 1.0 or len(df) == 0:
        return pd.DataFrame()
    n = max(int(len(df) * (n_mult - 1.0)), 1)
    part = df.iloc[rng.choice(len(df), size=n, replace=True)].copy().reset_index(drop=True)
    part["is_augmented"] = 1
    part["aug_type"] = "bootstrap"
    part["sample_weight"] = weight
    return part


def augment_missingness(df, p_drop, weight, rng):
    if len(df) == 0:
        return pd.DataFrame()
    pick = df.sample(frac=min(max(p_drop, 0.0), 1.0), random_state=int(rng.integers(1_000_000_000))).copy()
    for col in SOCIAL_COLS:
        obs = f"{col}_observed"
        if col in pick.columns and obs in pick.columns:
            m = pick[obs] == 1
            pick.loc[m, obs] = 0.0
            pick.loc[m, col] = np.nan
    pick["is_augmented"] = 1
    pick["aug_type"] = "missingness"
    pick["sample_weight"] = weight
    return pick.reset_index(drop=True)


def augment_cohort_jitter(df, sigma, weight, rng, sport_key):
    jitter_cols = [c for c in CFB_STAT_COLS if c in df.columns]
    jitter_cols += [c for c in df.columns if c.startswith("json_stat_")]
    if not jitter_cols or len(df) == 0:
        return pd.DataFrame()
    frac = min(0.5, max(0.1, 50.0 / max(len(df), 1)))
    part = df.sample(frac=frac, random_state=int(rng.integers(1_000_000_000))).copy()
    for col in jitter_cols:
        obs = f"{col}_observed"
        noise = rng.normal(1.0, sigma, size=len(part))
        if obs in part.columns:
            m = (part[obs] == 1).values
            part.loc[m, col] = part.loc[m, col].values * noise[m]
        else:
            part[col] = part[col].values * noise
    part["is_augmented"] = 1
    part["aug_type"] = "cohort_jitter"
    part["sample_weight"] = weight
    return part.reset_index(drop=True)


def augment_school_swap(df, p_swap, weight, rng):
    if p_swap <= 0 or "school_clean" not in df.columns or "conference" not in df.columns or len(df) == 0:
        return pd.DataFrame()
    schools = df["school_clean"].dropna().unique().tolist()
    if len(schools) < 2:
        return pd.DataFrame()
    part = df.sample(frac=min(p_swap, 0.25), random_state=int(rng.integers(1_000_000_000))).copy()
    conf_map = df.groupby("school_clean")["conference"].agg(
        lambda s: s.mode().iloc[0] if len(s.dropna()) else np.nan).to_dict()
    p5 = [s for s, c in conf_map.items() if c in P5_CONFERENCES]
    g5 = [s for s in schools if s not in p5]
    out_rows = []
    for _, row in part.iterrows():
        new = row.copy()
        if rng.random() < 0.5 and p5 and g5:
            new["school_clean"] = rng.choice(g5 if row.get("is_p5", 0) == 1 else p5)
            new["conference"] = conf_map.get(new["school_clean"], new.get("conference"))
            new["is_p5"] = float(new["conference"] in P5_CONFERENCES)
        new["is_augmented"] = 1
        new["aug_type"] = "school_swap"
        new["sample_weight"] = weight
        out_rows.append(new)
    return pd.DataFrame(out_rows) if out_rows else pd.DataFrame()


def build_augmented_train(real_train, sport_key, aug_flags, rng):
    base = real_train.copy()
    base["is_augmented"] = 0
    base["aug_type"] = "real"
    if "data_quality_score" in base.columns:
        base["sample_weight"] = base["data_quality_score"].fillna(0.5).clip(0.2, 1.0)
    else:
        base["sample_weight"] = 0.7
    parts = [
        base,
        augment_bootstrap(base, aug_flags.get("bootstrap_multiplier", 1.5), 0.95, rng),
        augment_missingness(base, aug_flags.get("missingness_p", 0.25), 0.55, rng),
        augment_cohort_jitter(base, aug_flags.get("jitter_sigma", 0.05), 0.45, rng, sport_key),
        augment_school_swap(base, aug_flags.get("school_swap_p", 0.0), 0.30, rng),
    ]
    return pd.concat([p for p in parts if len(p)], ignore_index=True)


def feature_matrix(df, objective, fixed_cols=None):
    if fixed_cols is not None:
        num = [c for c in fixed_cols if not c.endswith("_observed")]
        masks = [c for c in fixed_cols if c.endswith("_observed")]
        X_num = df.reindex(columns=num).apply(pd.to_numeric, errors="coerce").fillna(0.0).values
        X_mask = df.reindex(columns=masks).fillna(0.0).values if masks else None
        X = np.hstack([X_num, X_mask]) if X_mask is not None else X_num
        return X, list(fixed_cols)

    leaked = _leaked_columns(df.columns, objective)
    exclude = set(META_COLS) | leaked
    exclude |= {c for c in df.columns if c.startswith("target_") or c.startswith("label_") or c.endswith("_raw")}
    exclude |= {c for c in df.columns if c.startswith("json_") and not c.startswith("json_stat_")}

    numeric_cols = []
    for c in df.columns:
        if c in exclude or c.endswith("_observed") or c.endswith("_imputed_from"):
            continue
        if df[c].dtype == object:
            continue
        if pd.to_numeric(df[c], errors="coerce").notna().sum() < max(10, len(df) * 0.02):
            continue
        numeric_cols.append(c)
    numeric_cols = sorted(set(numeric_cols))

    mask_cols = sorted(c for c in df.columns
                       if c.endswith("_observed") and c not in leaked and c[:-9] not in leaked)

    X_num = df[numeric_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0).values
    if mask_cols:
        X = np.hstack([X_num, df[mask_cols].fillna(0.0).values])
    else:
        X = X_num
    return X, numeric_cols + mask_cols


def target_column(objective):
    return {
        "value_nil": "target_log_nil_usd",
        "value_proxy_ig": "target_log_ig",
        "quality": "target_quality",
        "quality_external": "target_quality_external",
    }[objective]


def train_objective(df, sport_key, objective, rng):
    tcol = target_column(objective)
    if tcol not in df.columns:
        return {"objective": objective, "status": "skipped",
                "reason": f"target '{tcol}' not present (no stats/labels parsed for {sport_key})"}
    work = df[df[tcol].notna()].copy()
    if len(work) < 20:
        return {"objective": objective, "status": "skipped", "reason": f"too few labeled rows ({len(work)})"}

    # Degeneracy guard: refuse to train on placeholder-dominated / near-constant labels.
    # (e.g. CFB instagram_followers is mostly a seeded 2500 default, not scraped reality.)
    yv = work[tcol].astype(float)
    top_frac = float(yv.value_counts(normalize=True).iloc[0]) if len(yv) else 1.0
    if yv.nunique() < 10 or top_frac > 0.6 or yv.std(ddof=0) < 1e-6:
        return {"objective": objective, "status": "skipped",
                "reason": (f"degenerate target: {yv.nunique()} unique values, "
                           f"top value = {top_frac*100:.0f}% of {len(yv)} rows (placeholder?)")}

    sort_col = "scraped_at" if "scraped_at" in work.columns else work.columns[0]
    work = work.sort_values(sort_col)
    n = len(work)
    i1, i2 = int(n * 0.70), int(n * 0.85)
    train_real, val_real, test_real = work.iloc[:i1], work.iloc[i1:i2], work.iloc[i2:]

    aug_flags = AUG_FLAGS.get(sport_key, AUG_FLAGS["cfb"])
    train_aug = build_augmented_train(train_real, sport_key, aug_flags, rng)

    X_train, feat_names = feature_matrix(train_aug, objective)
    y_train = train_aug[tcol].astype(float).values
    w_train = train_aug["sample_weight"].astype(float).values
    X_val, _ = feature_matrix(val_real, objective, fixed_cols=feat_names)
    X_test, _ = feature_matrix(test_real, objective, fixed_cols=feat_names)

    model = GradientBoostingRegressor(n_estimators=120, max_depth=4, learning_rate=0.08,
                                      subsample=0.85, random_state=RANDOM_SEED)
    model.fit(X_train, y_train, sample_weight=w_train)

    def _metrics(y_true, pred):
        if len(y_true) == 0:
            return {}
        mae = float(mean_absolute_error(y_true, pred))
        rmse = float(mean_squared_error(y_true, pred) ** 0.5)
        spear = float(pd.Series(y_true).corr(pd.Series(pred), method="spearman")) if len(y_true) > 2 else None
        return {"mae": round(mae, 4), "rmse": round(rmse, 4),
                "spearman": round(spear, 4) if spear is not None and pd.notna(spear) else None,
                "target_std": round(float(np.std(y_true)), 4), "n": int(len(y_true))}

    return {
        "objective": objective, "status": "ok", "target_col": tcol,
        "train_rows_real": len(train_real), "train_rows_aug": len(train_aug),
        "val_rows": len(val_real), "test_rows": len(test_real), "n_features": len(feat_names),
        "validation": _metrics(val_real[tcol].astype(float).values, model.predict(X_val)),
        "test": _metrics(test_real[tcol].astype(float).values, model.predict(X_test)),
        "model": model, "feature_names": feat_names,
    }


def export_bundle(sport_key, objective, result, cfg):
    if result.get("status") != "ok" or not EXPORT_MODELS:
        return None
    obj = {
        "value_nil": "value", "value_proxy_ig": "value_ig",
        "quality": "quality", "quality_external": "quality",
    }.get(objective, objective)
    version = "1.0.0-colab"
    model_key = f"gravity_athlete_{sport_key}_{obj}_v1"
    out_dir = ARTIFACT_DIR / sport_key / model_key / version
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "model.pkl", "wb") as fh:
        pickle.dump(result["model"], fh)
    (out_dir / "feature_manifest.json").write_text(json.dumps({"feature_names": result["feature_names"]}, indent=2))
    (out_dir / "metrics.json").write_text(json.dumps(
        {"validation": result.get("validation"), "test": result.get("test"), "objective": objective}, indent=2))
    (out_dir / "training_manifest.json").write_text(json.dumps({
        "model_key": model_key, "entity_type": "athlete", "sport": sport_key, "objective": obj,
        "version": version, "row_count": result.get("train_rows_aug"),
        "source": "gravity_exports_eda_train_by_sport.ipynb"}, indent=2))
    return out_dir


# ----------------------------- EDA -----------------------------

def eda_report(df, sport_key, cfg):
    print(f"\n{'='*64}\nEDA — {sport_key.upper()}   rows={len(df)}  cols={len(df.columns)}\n{'='*64}")
    print("Schools:", df["school"].nunique() if "school" in df.columns else "n/a",
          "| Positions:", df["position"].nunique() if "position" in df.columns else "n/a")

    if "conference_imputed_from" in df.columns:
        print("\nConference source breakdown:", df["conference_imputed_from"].value_counts().to_dict())
    if cfg["conference_parse"] == "division" and "division" in df.columns:
        print("Division top:", df["division"].value_counts().head(5).to_dict())
    elif "conference" in df.columns:
        print("Clean conference top:", df["conference"].value_counts().head(6).to_dict())

    print("\nTarget / signal coverage:")
    for col in ["nil_valuation", "instagram_followers", "twitter_followers", "proof_proxy"]:
        if col in df.columns:
            s = pd.to_numeric(df[col], errors="coerce")
            print(f"  {col:22s} non-null={int(s.notna().sum()):5d}  >0={int((s.fillna(0) > 0).sum()):5d}")

    stat_cols = [c for c in CFB_STAT_COLS if c in df.columns] + [c for c in df.columns if c.startswith("json_stat_")]
    if stat_cols:
        cov = df[stat_cols].notna().mean().mean()
        print(f"\nStat columns: {len(stat_cols)}  mean fill={cov*100:.1f}%  e.g. {stat_cols[:6]}")
    else:
        print("\nStat columns: none parsed")

    if "position" in df.columns:
        print("\nTop positions:", df["position"].value_counts().head(8).to_dict())

    null_pct = (df.isna().mean().sort_values(ascending=False).head(10) * 100).round(1)
    print("\nTop missing %:")
    for c, p in null_pct.items():
        if p > 0:
            print(f"  {c:30s} {p:5.1f}%")


def plot_eda(df, sport_key, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    panels = []
    miss = (df.isna().mean().sort_values(ascending=False).head(15) * 100)
    panels.append(("missingness", miss))
    fig, axes = plt.subplots(1, 3, figsize=(16, 4))

    axes[0].barh(miss.index[::-1], miss.values[::-1], color="#c0504d")
    axes[0].set_title(f"{sport_key} top missing %")
    axes[0].tick_params(labelsize=7)

    # target distribution
    tcol = "target_log_nil_usd" if "target_log_nil_usd" in df.columns and df["target_log_nil_usd"].notna().sum() > 20 else (
        "target_quality" if "target_quality" in df.columns else None)
    if tcol:
        vals = df[tcol].dropna()
        axes[1].hist(vals, bins=30, color="#4f81bd")
        axes[1].set_title(f"{sport_key} {tcol} dist (n={len(vals)})")
    else:
        axes[1].text(0.5, 0.5, "no target", ha="center")
        axes[1].set_title(f"{sport_key} target")

    # value/quality by position group
    grp = "position_group" if "position_group" in df.columns else "position"
    metric = "nil_valuation" if (("nil_valuation" in df.columns) and df["nil_valuation"].fillna(0).gt(0).sum() > 10) else (
        "proof_proxy" if "proof_proxy" in df.columns else None)
    if metric and grp in df.columns:
        sub = df[df[metric].notna()]
        if metric == "nil_valuation":
            sub = sub[sub[metric] > 0]
        order = list(sub.groupby(grp)[metric].median().sort_values(ascending=False).head(10).index)
        data = [sub[sub[grp] == g][metric].values for g in order]
        if data:
            axes[2].boxplot(data)
            axes[2].set_xticks(range(1, len(order) + 1))
            axes[2].set_xticklabels(order, rotation=90, fontsize=7)
            axes[2].set_title(f"{sport_key} {metric} by {grp}")
    else:
        axes[2].text(0.5, 0.5, "no metric", ha="center")
        axes[2].set_title(f"{sport_key} by position")

    plt.tight_layout()
    plt.savefig(out_dir / f"{sport_key}_eda.png", dpi=110)
    try:
        plt.show()
    except Exception:
        pass
    plt.close(fig)


def run_sport_pipeline(sport_key: str) -> dict:
    cfg = SPORT_CONFIG[sport_key]
    seed_offset = list(SPORT_CONFIG.keys()).index(sport_key)
    rng = np.random.default_rng(RANDOM_SEED + seed_offset)
    sport_art = ARTIFACT_DIR / sport_key
    sport_art.mkdir(parents=True, exist_ok=True)

    print(f"\n\n{'#'*70}\n# SPORT: {sport_key.upper()}\n{'#'*70}")
    df = load_sport(sport_key, cfg)
    df = flatten_raw_json(df)      # FIX: parse JSON before numeric coercion
    df = clean_dataframe(df, sport_key, cfg)
    df = apply_imputation(df, sport_key)
    df = extract_features(df, sport_key)

    eda_report(df, sport_key, cfg)
    try:
        plot_eda(df, sport_key, sport_art)
    except Exception as e:
        print("Plot skipped:", e)

    df.to_csv(sport_art / f"{sport_key}_clean_features.csv", index=False)

    results = {"sport": sport_key, "rows": len(df), "objectives": {}}
    for objective in cfg.get("train_objectives", []):
        res = train_objective(df, sport_key, objective, rng)
        results["objectives"][objective] = {k: v for k, v in res.items() if k not in ("model", "feature_names")}
        if res.get("status") == "ok":
            print(f"Train {objective:15s} -> val={res.get('validation')}  test={res.get('test')}  feats={res.get('n_features')}")
            blocked = set(cfg.get("blocked_export_objectives") or [])
            if objective in cfg.get("export_objectives", []) and objective not in blocked:
                path = export_bundle(sport_key, objective, res, cfg)
                if path:
                    print("  exported:", path)
        else:
            print(f"Train {objective:15s} -> SKIPPED ({res.get('reason')})")
    return results


def record_result(result: dict) -> None:
    """Keep ALL_RESULTS unique-by-sport so PART 6 works after per-sport runs."""
    global ALL_RESULTS
    try:
        ALL_RESULTS
    except NameError:
        ALL_RESULTS = []
    ALL_RESULTS = [r for r in ALL_RESULTS if r.get("sport") != result.get("sport")]
    ALL_RESULTS.append(result)


print("Utilities loaded.")
'''

cells.append(code(UTILS))

cells.append(md("""---
## PART 0 — Run all configured sports

Each sport runs an isolated pipeline (EDA → clean → impute → augment → train) and writes
artifacts under `artifacts/{sport}/`. Set `RUN_SPORTS` in the config cell."""))

cells.append(code('''#@title 0.5 Execute all pipelines
ALL_RESULTS = []
for sport_key in RUN_SPORTS:
    if sport_key not in SPORT_CONFIG:
        print("Unknown sport:", sport_key)
        continue
    try:
        res = run_sport_pipeline(sport_key)
        record_result(res)
    except FileNotFoundError as e:
        print(f"SKIP {sport_key}: {e}")
    except Exception as e:
        import traceback
        print(f"ERROR {sport_key}: {e}")
        traceback.print_exc()'''))

cells.append(md("""---
## PART 1 — CFB (College Football)

Richest export (~6.8K rows, 461 NIL). Trains NIL value, Instagram-proxy value, and
stat-based quality. EDA panel + metrics below."""))
cells.append(code('''#@title 1 CFB only
cfb_result = run_sport_pipeline("cfb")
record_result(cfb_result)
pd.DataFrame([{"objective": k, **v} for k, v in cfb_result["objectives"].items()])'''))

cells.append(md("""---
## PART 2 — NFL

Division parsed from standing strings. Quality from `season_stats` in `raw_data_json`.
Value training deferred until contract/social labels exist."""))
cells.append(code('''#@title 2 NFL only
nfl_result = run_sport_pipeline("nfl")
record_result(nfl_result)
pd.DataFrame([{"objective": k, **v} for k, v in nfl_result["objectives"].items()])'''))

cells.append(md("""---
## PART 3 — NCAAB Men's

Stats extracted from `raw_data_json.season_stats` (points, rebounds, assists, minutes…).
Quality model primary."""))
cells.append(code('''#@title 3 NCAAB Men's only
ncaab_m_result = run_sport_pipeline("ncaab_mens")
record_result(ncaab_m_result)
pd.DataFrame([{"objective": k, **v} for k, v in ncaab_m_result["objectives"].items()])'''))

cells.append(md("""---
## PART 4 — NCAAB Women's

Separate pipeline from men's — independent scalers, medians, and models."""))
cells.append(code('''#@title 4 NCAAB Women's only
ncaab_w_result = run_sport_pipeline("ncaab_womens")
record_result(ncaab_w_result)
pd.DataFrame([{"objective": k, **v} for k, v in ncaab_w_result["objectives"].items()])'''))

cells.append(md("""---
## PART 5 — WNBA

Small-N (~200 rows). Bootstrap-heavy augmentation; **do not promote** without more data."""))
cells.append(code('''#@title 5 WNBA only
wnba_result = run_sport_pipeline("wnba")
record_result(wnba_result)
pd.DataFrame([{"objective": k, **v} for k, v in wnba_result["objectives"].items()])'''))

cells.append(md("""---
## PART 6 — Cross-sport summary

Test metrics use **real-only** holdout rows (augmentation applied to train only)."""))
cells.append(code('''#@title 6.1 Results summary table
summary_rows = []
for res in ALL_RESULTS:
    for obj, m in res.get("objectives", {}).items():
        test = m.get("test") or {}
        val = m.get("validation") or {}
        summary_rows.append({
            "sport": res["sport"], "objective": obj, "status": m.get("status"),
            "rows_total": res["rows"], "train_real": m.get("train_rows_real"),
            "train_aug": m.get("train_rows_aug"), "test_n": test.get("n"),
            "val_mae": val.get("mae"), "test_mae": test.get("mae"),
            "test_spearman": test.get("spearman"),
        })
summary_df = pd.DataFrame(summary_rows)
summary_df'''))

cells.append(code('''#@title 6.2 Download artifacts (Colab)
import shutil
try:
    from google.colab import files
    zip_path = shutil.make_archive("gravity_artifacts", "zip", ARTIFACT_DIR)
    files.download(zip_path)
except ImportError:
    print("Artifacts saved locally at", ARTIFACT_DIR.resolve())'''))

cells.append(md("""---
## Appendix — Augmentation reference

| Type | Weight | Description |
|------|--------|-------------|
| real | DQS (0.2–1.0) | Original row, weighted by data quality |
| bootstrap | 0.95 | Resample with replacement |
| missingness | 0.55 | Drop social observations, mask=0 |
| cohort_jitter | 0.45 | ±sigma noise on stats |
| school_swap | 0.30 | CFB counterfactual market (P5↔G5) |

**Split policy:** chronological 70/15/15 on real rows → augment **train only** → evaluate on real test.
**Leakage guard:** target-derived columns excluded per objective by token match — e.g. `value_nil`
drops every `*nil_valuation*` / `*nil_deal*` alias, `value_proxy_ig` drops every `*instagram*` alias.

> **Caveat — `quality` target is a self-supervised proxy.** `target_quality` is `proof_proxy`,
> a standardized composite of the same `json_stat_*` / CFB stat columns that are also fed in as
> features. The model therefore *reconstructs* the composite, so the very high Spearman (~0.99) is
> expected and **does not** indicate generalization to an independent quality ground truth. Treat
> `value_nil` (real labels) as the trustworthy supervised metric. Replace `proof_proxy` with an
> external quality label (awards, NFL draft grade, advanced metrics) before promoting a quality model."""))

nb = {
    "nbformat": 4, "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "version": "3.10"},
        "accelerator": "GPU", "colab": {"provenance": []},
    },
    "cells": cells,
}

out = Path(__file__).parent / "gravity_exports_eda_train_by_sport.ipynb"
out.write_text(json.dumps(nb, indent=1), encoding="utf-8")
print("Wrote", out, "cells:", len(cells))
