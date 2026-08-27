"""CSC report response models must not strip deal-scope or driver evidence."""

from gravity_api.routers.reports import CscKeyDriverOut, CscValueOut


def test_csc_value_out_preserves_deal_scopes():
    out = CscValueOut.model_validate(
        {
            "total_benchmark": 3_700_000,
            "activation_deal_mid": 53_200,
            "deal_confidence": "Uncalibrated",
            "selected_deal_scope": "standard_activation",
            "deal_scopes": {
                "standard_activation": {
                    "scope": "standard_activation",
                    "label": "Standard activation",
                    "low": 25_500,
                    "mid": 53_200,
                    "high": 93_100,
                    "qualified_transactions": 12,
                    "readiness": "insufficient_data",
                    "confidence": "Uncalibrated",
                    "calibrated": False,
                }
            },
            "range_note": "Activation range is separate from the annual benchmark.",
        }
    )
    assert out.deal_scopes is not None
    scoped = out.deal_scopes["standard_activation"]
    assert scoped.mid == 53_200
    assert scoped.qualified_transactions == 12
    assert scoped.readiness == "insufficient_data"
    assert out.selected_deal_scope == "standard_activation"
    assert out.range_note is not None


def test_csc_key_driver_out_preserves_supporting_signals():
    out = CscKeyDriverOut.model_validate(
        {
            "label": "Brand Strength",
            "signal": "High",
            "explanation": "Brand is the primary commercial driver.",
            "supporting_signals": [{"label": "Instagram", "value": "245K"}],
            "supporting_metrics": [
                {"label": "Instagram", "value": 245_000, "unit": "followers"}
            ],
        }
    )
    assert out.supporting_signals[0].value == "245K"
    assert out.supporting_metrics[0].value == 245_000
