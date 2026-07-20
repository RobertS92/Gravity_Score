#!/usr/bin/env python3
"""Research-backed calibration scores for the 54-player NFL heat-check panel.

Scoring mirrors gravity_composite NFL weights:
  G = 0.26·Brand + 0.30·Proof + 0.20·Proximity + 0.16·Velocity + 0.08·(100 − Risk)

Risk is decomposed like the production pipeline (injury / conduct / age) but injury
is discounted by position group because commercial pull decays differently:
  - QB brand persists on IR (Burrow still moves jerseys/deals)
  - RB availability is most endorsement-sensitive (McCaffrey)
  - OL/K have low brand baselines so injury matters less to Gravity

The ML bundle learns non-linear interactions; this heuristic layer keeps injury
and conduct as separate inputs so we do not double-penalize star QBs/WRs.

Sources: 2025 NFL regular season stats (PFR/NFL.com), AP All-Pro 2025,
Sportico earnings, ESPN injury reports, NFL personal conduct policy cases.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from gravity_composite.composite import compute_gravity_raw, get_composite_weights

STATS_SEASON = 2025

# How much raw injury/availability hits *commercial* gravity by position (0–1).
# 1.0 = full penalty; QB at 0.50 means half the games-missed drag on Risk.
POSITION_INJURY_COMMERCIAL_MULT: dict[str, float] = {
    "QB": 0.50,
    "RB": 1.00,
    "WR": 0.70,
    "TE": 0.75,
    "OL": 0.45,
    "DL": 0.55,
    "LB": 0.55,
    "DB": 0.60,
    "K": 0.40,
}


def compute_commercial_risk(
    group: str,
    *,
    injury_raw: float,
    conduct_raw: float,
    age_raw: float = 10.0,
) -> int:
    """Map sub-scores to 0–100 Risk (higher = worse).

    Mirrors data_pipeline.py split (~40% injury, ~50% conduct, ~10% age) but
    scales injury by position commercial multiplier first.
    """
    mult = POSITION_INJURY_COMMERCIAL_MULT.get(group, 0.65)
    injury_commercial = min(100.0, injury_raw * mult)
    risk = 0.40 * injury_commercial + 0.50 * conduct_raw + 0.10 * age_raw
    return int(round(min(95.0, max(8.0, risk))))


@dataclass
class PlayerScore:
    group: str
    tier: str
    name: str
    brand: int
    proof: int
    proximity: int
    velocity: int
    injury_raw: float
    conduct_raw: float
    age_raw: float = 10.0
    risk_notes: str = ""

    @property
    def risk(self) -> int:
        return compute_commercial_risk(
            self.group,
            injury_raw=self.injury_raw,
            conduct_raw=self.conduct_raw,
            age_raw=self.age_raw,
        )

    @property
    def gravity(self) -> float:
        return round(
            compute_gravity_raw(
                brand=float(self.brand),
                proof=float(self.proof),
                proximity=float(self.proximity),
                velocity=float(self.velocity),
                risk=float(self.risk),
                sport="nfl",
            ),
            1,
        )


# fmt: off
# injury_raw / conduct_raw / age_raw are 0–100 sub-scores BEFORE position injury discount.
# risk_notes embed 2025 season stat lines where relevant.
PANEL: list[PlayerScore] = [
    # ── QB ─────────────────────────────────────────────────────────────────
    PlayerScore("QB", "Star", "Patrick Mahomes", 91, 96, 95, 78,
                injury_raw=20, conduct_raw=8, age_raw=12,
                risk_notes="2025: 16 GP, 4,028 yds, 28 TD; durable"),
    PlayerScore("QB", "Star", "Josh Allen", 84, 92, 88, 74,
                injury_raw=25, conduct_raw=10, age_raw=14,
                risk_notes="2025: 17 GP, 3,731 yds, 25 TD; steady"),
    PlayerScore("QB", "Elite", "Lamar Jackson", 78, 93, 82, 76,
                injury_raw=35, conduct_raw=10, age_raw=14,
                risk_notes="2025: 17 GP, 4,172 yds, 29 TD; MVP-caliber"),
    PlayerScore("QB", "Elite", "Joe Burrow", 84, 86, 80, 68,
                injury_raw=72, conduct_raw=8, age_raw=12,
                risk_notes="2025: 8 GP, 1,809 yds, 17 TD; turf toe (9 missed); QB injury discount"),
    PlayerScore("QB", "Starter", "Trevor Lawrence", 72, 88, 74, 82,
                injury_raw=22, conduct_raw=10, age_raw=10,
                risk_notes="2025: 17 GP, 4,007 yds, 29 TD; breakout velocity"),
    PlayerScore("QB", "Starter", "Kirk Cousins", 52, 58, 62, 28,
                injury_raw=55, conduct_raw=8, age_raw=30,
                risk_notes="2025: ATL backup, 10 GP minimal; age 37"),

    # ── RB ─────────────────────────────────────────────────────────────────
    PlayerScore("RB", "Star", "Christian McCaffrey", 72, 96, 78, 88,
                injury_raw=38, conduct_raw=10, age_raw=18,
                risk_notes="2025: 17 GP, 1,202 rush + 924 rec = 2,126 scrimmage; comeback surge"),
    PlayerScore("RB", "Star", "Saquon Barkley", 77, 90, 74, 52,
                injury_raw=30, conduct_raw=8, age_raw=14,
                risk_notes="2025: 16 GP, 1,140 rush; down from 2024 record pace"),
    PlayerScore("RB", "Elite", "Derrick Henry", 70, 92, 72, 68,
                injury_raw=28, conduct_raw=8, age_raw=22,
                risk_notes="2025: 16 GP, 1,595 rush, 16 TD; age 31 still elite"),
    PlayerScore("RB", "Elite", "Jonathan Taylor", 62, 90, 68, 72,
                injury_raw=42, conduct_raw=10, age_raw=12,
                risk_notes="2025: 16 GP, 1,585 rush, 18 TD; healthy bounce-back"),
    PlayerScore("RB", "Starter", "Kenneth Walker III", 55, 78, 58, 62,
                injury_raw=48, conduct_raw=10, age_raw=8,
                risk_notes="2025: 14 GP, 876 rush; groin/ankle recurrences"),
    PlayerScore("RB", "Starter", "James Conner", 50, 62, 52, 35,
                injury_raw=78, conduct_raw=10, age_raw=16,
                risk_notes="2025: 3 GP; season-ending injury"),

    # ── WR ─────────────────────────────────────────────────────────────────
    PlayerScore("WR", "Star", "Justin Jefferson", 74, 82, 80, 48,
                injury_raw=28, conduct_raw=8, age_raw=10,
                risk_notes="2025: 17 GP, 84 rec, 1,048 yds, 2 TD; down vs 2024 All-Pro"),
    PlayerScore("WR", "Star", "Tyreek Hill", 86, 42, 74, 22,
                injury_raw=82, conduct_raw=55, age_raw=14,
                risk_notes="2025: 4 GP, 265 yds; season-ending knee; DV investigation ongoing"),
    PlayerScore("WR", "Elite", "CeeDee Lamb", 76, 88, 78, 65,
                injury_raw=32, conduct_raw=10, age_raw=10,
                risk_notes="2025: 15 GP, 101 rec, 1,194 yds, 6 TD; shoulder missed time"),
    PlayerScore("WR", "Elite", "Amon-Ra St. Brown", 72, 92, 72, 75,
                injury_raw=18, conduct_raw=8, age_raw=10,
                risk_notes="2025: 17 GP, 117 rec, 1,401 yds, 11 TD; AP 2nd team"),
    PlayerScore("WR", "Starter", "Courtland Sutton", 58, 80, 62, 55,
                injury_raw=35, conduct_raw=10, age_raw=12,
                risk_notes="2025: 16 GP, 81 rec, 1,033 yds, 8 TD; steady WR1"),
    PlayerScore("WR", "Starter", "DJ Moore", 60, 76, 64, 50,
                injury_raw=22, conduct_raw=10, age_raw=12,
                risk_notes="2025: 16 GP, 82 rec, 966 yds, 6 TD; CHI WR1"),

    # ── TE ─────────────────────────────────────────────────────────────────
    PlayerScore("TE", "Star", "Travis Kelce", 92, 78, 84, 42,
                injury_raw=32, conduct_raw=10, age_raw=28,
                risk_notes="2025: 17 GP, 76 rec, 851 yds, 5 TD; Pro Bowl, on-field fade"),
    PlayerScore("TE", "Star", "Trey McBride", 68, 94, 68, 88,
                injury_raw=15, conduct_raw=8, age_raw=8,
                risk_notes="2025: 16 GP, 126 rec, 1,239 yds, 11 TD; AP 1st team TE"),
    PlayerScore("TE", "Elite", "George Kittle", 70, 86, 70, 58,
                injury_raw=52, conduct_raw=10, age_raw=18,
                risk_notes="2025: 15 GP, 78 rec, 1,015 yds, 7 TD; soft-tissue history"),
    PlayerScore("TE", "Elite", "Mark Andrews", 62, 74, 62, 45,
                injury_raw=55, conduct_raw=10, age_raw=14,
                risk_notes="2025: 14 GP, 55 rec, 673 yds, 7 TD; down from peak"),
    PlayerScore("TE", "Starter", "David Njoku", 54, 76, 55, 52,
                injury_raw=38, conduct_raw=10, age_raw=12,
                risk_notes="2025: 15 GP, 64 rec, 672 yds, 5 TD"),
    PlayerScore("TE", "Starter", "Evan Engram", 50, 68, 52, 40,
                injury_raw=42, conduct_raw=10, age_raw=14,
                risk_notes="2025: 12 GP, 47 rec, 450 yds; limited DEN role"),

    # ── OL ─────────────────────────────────────────────────────────────────
    PlayerScore("OL", "Star", "Trent Williams", 48, 90, 72, 38,
                injury_raw=48, conduct_raw=8, age_raw=26,
                risk_notes="2025: 12 GP; age 37 LT; cancer history"),
    PlayerScore("OL", "Star", "Lane Johnson", 46, 88, 70, 36,
                injury_raw=45, conduct_raw=8, age_raw=24,
                risk_notes="2025: 13 GP; ankle; anxiety absence history"),
    PlayerScore("OL", "Elite", "Chris Lindstrom", 38, 86, 62, 50,
                injury_raw=20, conduct_raw=8, age_raw=10,
                risk_notes="2025: 17 GP; AP 2nd team guard"),
    PlayerScore("OL", "Elite", "Quenton Nelson", 42, 82, 64, 35,
                injury_raw=42, conduct_raw=8, age_raw=14,
                risk_notes="2025: 14 GP; injury-shortened"),
    PlayerScore("OL", "Starter", "Tyler Linderbaum", 36, 84, 58, 58,
                injury_raw=18, conduct_raw=8, age_raw=8,
                risk_notes="2025: 17 GP; ascending center"),
    PlayerScore("OL", "Starter", "Tyler Smith", 34, 82, 56, 62,
                injury_raw=15, conduct_raw=8, age_raw=8,
                risk_notes="2025: 17 GP; Pro Bowl guard trajectory"),

    # ── DL ─────────────────────────────────────────────────────────────────
    PlayerScore("DL", "Star", "Myles Garrett", 68, 98, 80, 92,
                injury_raw=18, conduct_raw=18, age_raw=14,
                risk_notes="2025: 17 GP, NFL-record 23 sacks; unanimous AP 1st team"),
    PlayerScore("DL", "Star", "Micah Parsons", 72, 90, 82, 72,
                injury_raw=65, conduct_raw=22, age_raw=10,
                risk_notes="2025: GB, 14 GP, 12 sacks; ACL Week 15; trade narrative"),
    PlayerScore("DL", "Elite", "Maxx Crosby", 66, 86, 68, 68,
                injury_raw=28, conduct_raw=25, age_raw=12,
                risk_notes="2025: 16 GP, 11.5 sacks; past substance ban"),
    PlayerScore("DL", "Elite", "Nick Bosa", 68, 72, 74, 38,
                injury_raw=75, conduct_raw=10, age_raw=12,
                risk_notes="2025: 3 GP, 2 sacks; season-ending injury"),
    PlayerScore("DL", "Starter", "Will Anderson Jr.", 58, 90, 62, 85,
                injury_raw=18, conduct_raw=8, age_raw=8,
                risk_notes="2025: 17 GP, 12 sacks; AP 1st team edge"),
    PlayerScore("DL", "Starter", "Montez Sweat", 52, 78, 58, 52,
                injury_raw=30, conduct_raw=10, age_raw=12,
                risk_notes="2025: 16 GP, 8 sacks; CHI edge"),

    # ── LB ─────────────────────────────────────────────────────────────────
    PlayerScore("LB", "Star", "T.J. Watt", 66, 84, 80, 55,
                injury_raw=38, conduct_raw=10, age_raw=14,
                risk_notes="2025: 14 GP, 7 sacks; Pro Bowl, not AP 1st"),
    PlayerScore("LB", "Star", "Fred Warner", 58, 82, 70, 42,
                injury_raw=72, conduct_raw=8, age_raw=14,
                risk_notes="2025: 6 GP; ankle truncated season"),
    PlayerScore("LB", "Elite", "Roquan Smith", 52, 86, 68, 58,
                injury_raw=22, conduct_raw=8, age_raw=12,
                risk_notes="2025: 17 GP, 89 tackles; AP 2nd team"),
    PlayerScore("LB", "Elite", "Devin Lloyd", 48, 82, 58, 72,
                injury_raw=22, conduct_raw=8, age_raw=8,
                risk_notes="2025: 16 GP, 102 tackles; young riser"),
    PlayerScore("LB", "Starter", "Zaire Franklin", 42, 78, 52, 55,
                injury_raw=28, conduct_raw=8, age_raw=12,
                risk_notes="2025: 17 GP, 173 tackles; IND leader"),
    PlayerScore("LB", "Starter", "Jerome Baker", 40, 74, 50, 48,
                injury_raw=35, conduct_raw=8, age_raw=12,
                risk_notes="2025: 14 GP, 95 tackles; MIA ILB"),

    # ── DB ─────────────────────────────────────────────────────────────────
    PlayerScore("DB", "Star", "Patrick Surtain II", 62, 90, 72, 62,
                injury_raw=18, conduct_raw=8, age_raw=10,
                risk_notes="2025: 16 GP, 4 INT; AP 2nd team (not DPOY repeat)"),
    PlayerScore("DB", "Star", "Sauce Gardner", 68, 82, 70, 52,
                injury_raw=25, conduct_raw=10, age_raw=10,
                risk_notes="2025: 15 GP, 2 INT; solid but not 2023 peak"),
    PlayerScore("DB", "Elite", "Minkah Fitzpatrick", 58, 84, 68, 45,
                injury_raw=48, conduct_raw=10, age_raw=14,
                risk_notes="2025: 12 GP; calf/leg injuries"),
    PlayerScore("DB", "Elite", "Jalen Ramsey", 66, 84, 72, 50,
                injury_raw=40, conduct_raw=12, age_raw=16,
                risk_notes="2025: 14 GP, 3 INT; MIA CB1"),
    PlayerScore("DB", "Starter", "L'Jarius Sneed", 52, 80, 58, 52,
                injury_raw=28, conduct_raw=10, age_raw=12,
                risk_notes="2025: 16 GP; TEN CB1 after trade"),
    PlayerScore("DB", "Starter", "Brian Branch", 54, 82, 60, 68,
                injury_raw=20, conduct_raw=8, age_raw=8,
                risk_notes="2025: 17 GP, 3 INT; DET rising safety"),

    # ── K ──────────────────────────────────────────────────────────────────
    PlayerScore("K", "Star", "Harrison Butker", 52, 84, 58, 52,
                injury_raw=12, conduct_raw=28, age_raw=14,
                risk_notes="2025: 17 GP, 33/38 FG; speech backlash"),
    PlayerScore("K", "Star", "Justin Tucker", 46, 55, 38, 18,
                injury_raw=20, conduct_raw=88, age_raw=24,
                risk_notes="2025: released May; 10-game conduct ban served"),
    PlayerScore("K", "Elite", "Evan McPherson", 38, 82, 48, 58,
                injury_raw=10, conduct_raw=8, age_raw=8,
                risk_notes="2025: 17 GP, 28/32 FG; clean"),
    PlayerScore("K", "Elite", "Jake Elliott", 36, 78, 50, 52,
                injury_raw=10, conduct_raw=8, age_raw=10,
                risk_notes="2025: 17 GP, 30/35 FG; steady"),
    PlayerScore("K", "Starter", "Brandon McManus", 32, 72, 44, 42,
                injury_raw=12, conduct_raw=72, age_raw=14,
                risk_notes="2025: GB kicker; London flight lawsuit under NFL review"),
    PlayerScore("K", "Starter", "Wil Lutz", 32, 76, 44, 48,
                injury_raw=10, conduct_raw=8, age_raw=12,
                risk_notes="2025: 17 GP, 29/33 FG; DEN; clean"),
]
# fmt: on

CSV_COLUMNS = [
    "season",
    "position_group",
    "tier",
    "athlete_name",
    "gravity_score",
    "brand",
    "proof",
    "proximity",
    "velocity",
    "risk",
    "brand_weighted",
    "proof_weighted",
    "proximity_weighted",
    "velocity_weighted",
    "risk_weighted",
    "injury_raw",
    "conduct_raw",
    "age_raw",
    "season_notes",
]


def panel_rows() -> list[dict[str, object]]:
    w = get_composite_weights("nfl")
    rows: list[dict[str, object]] = []
    for p in PANEL:
        risk = p.risk
        rows.append(
            {
                "season": STATS_SEASON,
                "position_group": p.group,
                "tier": p.tier,
                "athlete_name": p.name,
                "gravity_score": p.gravity,
                "brand": p.brand,
                "proof": p.proof,
                "proximity": p.proximity,
                "velocity": p.velocity,
                "risk": risk,
                "brand_weighted": round(w.brand * p.brand, 2),
                "proof_weighted": round(w.proof * p.proof, 2),
                "proximity_weighted": round(w.proximity * p.proximity, 2),
                "velocity_weighted": round(w.velocity * p.velocity, 2),
                "risk_weighted": round(w.risk * (100 - risk), 2),
                "injury_raw": p.injury_raw,
                "conduct_raw": p.conduct_raw,
                "age_raw": p.age_raw,
                "season_notes": p.risk_notes,
            }
        )
    return rows


def write_csv(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = panel_rows()
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def main() -> None:
    rows = panel_rows()

    print(f"NFL calibration panel — {STATS_SEASON} season stats\n")
    for group in ["QB", "RB", "WR", "TE", "OL", "DL", "LB", "DB", "K"]:
        print(f"\n## {group}")
        print(f"{'Tier':<8} {'Player':<24} {'G':>5}  {'B':>3} {'P':>3} {'X':>3} {'V':>3} {'R':>3}  2025 notes")
        print("-" * 100)
        for p in PANEL:
            if p.group != group:
                continue
            print(
                f"{p.tier:<8} {p.name:<24} {p.gravity:5.1f}  "
                f"{p.brand:3d} {p.proof:3d} {p.proximity:3d} {p.velocity:3d} {p.risk:3d}  "
                f"{p.risk_notes[:60]}"
            )

    csv_path = write_csv(
        Path(__file__).resolve().parents[1] / "reports" / f"calibration_panel_{STATS_SEASON}.csv"
    )
    print(f"\nWrote CSV: {csv_path}")
    print("\nJSON:", json.dumps(rows, indent=2))


if __name__ == "__main__":
    main()
