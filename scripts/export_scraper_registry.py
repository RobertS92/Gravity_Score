#!/usr/bin/env python3
"""Export scraper registry manifest to JSON or YAML for gravity-scrapers."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gravity_api.scraper_registry import build_registry  # noqa: E402
from gravity_api.services.scraper_registry_service import manifest_summary  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Export scraper registry manifest")
    parser.add_argument(
        "--out",
        type=Path,
        default=ROOT / "config" / "scraper_registry.json",
        help="Output file path (.json)",
    )
    args = parser.parse_args()

    payload = {
        "summary": manifest_summary(),
        "scrapers": [d.to_dict() for d in build_registry()],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {len(payload['scrapers'])} scrapers to {args.out}")


if __name__ == "__main__":
    main()
