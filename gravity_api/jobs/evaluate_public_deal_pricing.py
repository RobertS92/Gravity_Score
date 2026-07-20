"""Run the versioned 20-athlete public collective-package stress test."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from gravity_api.services.deal_pricing_validation import evaluate_public_collective_panel


FIXTURE = Path(__file__).resolve().parents[1] / "validation" / "public_collective_stress_20.json"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", choices=("baseline", "aggressive"), default="baseline")
    parser.add_argument("--json", action="store_true", help="Print the complete machine-readable result")
    args = parser.parse_args()

    dataset = json.loads(FIXTURE.read_text())
    result = evaluate_public_collective_panel(dataset["cases"], profile=args.profile)
    if args.json:
        print(json.dumps({"dataset": dataset, "result": result}, indent=2))
        return

    print(f"Dataset: {dataset['dataset_id']}")
    print(f"Profile: {result['profile']}")
    print(f"Coverage: {result['covered_n']}/{result['n']} ({result['coverage']:.1%})")
    print(f"QB coverage: {result['qb_covered_n']}/{result['qb_n']} ({result['qb_coverage']:.1%})")
    print(f"Median midpoint APE: {result['median_absolute_percentage_error']:.1%}")
    print(f"Mean midpoint APE: {result['mean_absolute_percentage_error']:.1%}")
    print(f"Median signed error: {result['median_signed_percentage_error']:.1%}")
    for row in result["rows"]:
        print(
            f"{row['athlete']}: reported ${row['reported_low_usd']:,.0f}–"
            f"${row['reported_high_usd']:,.0f}; predicted "
            f"${row['predicted_low_usd']:,.0f}–${row['predicted_high_usd']:,.0f}; "
            f"overlap={row['overlaps']}"
        )


if __name__ == "__main__":
    main()
