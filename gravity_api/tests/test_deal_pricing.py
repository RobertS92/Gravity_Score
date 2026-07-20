from gravity_api.services.deal_pricing import price_standard_activation


def _cohort(values):
    vals = sorted(values)
    return {
        "size": len(vals),
        "p10": vals[1],
        "p25": vals[4],
        "p50": vals[len(vals) // 2],
        "p75": vals[-5],
        "p90": vals[-2],
        "benchmark_values": vals,
    }


def test_deal_pricing_separates_annual_benchmark_from_activation_range():
    result = price_standard_activation(
        annual_benchmark=21_900_000,
        model_p50=4_600_000,
        cohort_stats=_cohort([300_000, 450_000, 700_000, 900_000, 1_200_000, 1_800_000, 2_500_000, 3_500_000, 5_000_000, 7_500_000]),
        comparables=[
            {"deal_value": 180_000, "dollar_p50_usd": 5_500_000},
            {"deal_value": 240_000, "dollar_p50_usd": 7_000_000},
            {"deal_value": 320_000, "dollar_p50_usd": 8_200_000},
        ],
        sport="CFB",
        position_group="QB",
        brand_score=96,
        proof_score=82,
        exposure_score=95,
        velocity_score=88,
        risk_score=12,
        model_confidence=0.78,
        verified_deals_count=3,
        cohort_fit="poor",
    )

    assert result.annual_nil_benchmark == 21_900_000
    assert result.activation_deal_low < result.activation_deal_mid < result.activation_deal_high
    assert result.activation_deal_high < result.annual_nil_benchmark * 0.08
    assert result.activation_deal_high < result.annual_nil_benchmark
    assert "standard 4-6 week activation" in result.basis


def test_twenty_athlete_panel_including_five_qbs_has_calibrated_activation_ranges():
    panel = [
        ("QB", 21_900_000, 325_000), ("QB", 4_200_000, 82_000), ("QB", 2_800_000, 58_000),
        ("QB", 1_100_000, 22_000), ("QB", 480_000, 9_500),
        ("WR", 1_700_000, 24_000), ("WR", 900_000, 13_000), ("RB", 750_000, 10_500),
        ("TE", 420_000, 6_200), ("OL", 300_000, 3_300),
        ("DL", 520_000, 5_500), ("LB", 360_000, 4_000), ("DB", 610_000, 6_800),
        ("G", 1_200_000, 22_000), ("WING", 950_000, 16_000), ("F", 700_000, 10_000),
        ("C", 550_000, 7_500), ("GUARD", 1_600_000, 30_000), ("WBB", 850_000, 16_000),
        ("OTHER", 180_000, 2_400),
    ]
    qb_count = sum(1 for pos, _, _ in panel if pos == "QB")
    covered = 0
    widths = []

    for idx, (position, annual, observed_deal) in enumerate(panel):
        sport = "WBB" if position == "WBB" else ("MBB" if position in {"G", "WING", "F", "C", "GUARD"} else "CFB")
        pos_group = "G" if position == "WBB" else position
        cohort_values = [annual * m for m in (0.35, 0.45, 0.55, 0.7, 0.85, 1.0, 1.15, 1.35, 1.6, 1.9)]
        comparables = [
            {"deal_value": observed_deal * 0.82, "dollar_p50_usd": annual * 0.82},
            {"deal_value": observed_deal * 1.04, "dollar_p50_usd": annual * 1.04},
            {"deal_value": observed_deal * 1.18, "dollar_p50_usd": annual * 1.18},
        ]
        result = price_standard_activation(
            annual_benchmark=annual,
            model_p50=annual * 0.92,
            cohort_stats=_cohort(cohort_values),
            comparables=comparables,
            sport=sport,
            position_group=pos_group,
            brand_score=70 + (idx % 5) * 5,
            proof_score=62 + (idx % 4) * 6,
            exposure_score=65 + (idx % 6) * 4,
            velocity_score=58 + (idx % 7) * 4,
            risk_score=12 + (idx % 6) * 5,
            model_confidence=0.66,
            verified_deals_count=2,
            cohort_fit="good",
        )
        assert result.activation_deal_low is not None
        assert result.activation_deal_high is not None
        assert result.activation_deal_high < annual
        assert result.activation_deal_high <= annual * (0.061 if position == "QB" else 0.046)
        if result.activation_deal_low <= observed_deal <= result.activation_deal_high:
            covered += 1
        widths.append((result.activation_deal_high - result.activation_deal_low) / result.activation_deal_mid)

    assert len(panel) == 20
    assert qb_count >= 5
    assert covered >= 16
    assert max(widths) < 1.8
