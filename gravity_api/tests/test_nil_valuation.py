"""NIL valuation sanitization."""

from gravity_api.services.nil_valuation import nil_from_row, sanitize_nil_valuation_usd


def test_arch_style_under_scale_multiplies_thousands() -> None:
    row = {
        "nil_valuation": 21866,
        "recruiting_stars": 5,
        "instagram_followers": 622000,
    }
    v = sanitize_nil_valuation_usd(21866, row)
    assert v is not None
    assert v >= 15_000_000


def test_nil_from_row_parses_m_suffix() -> None:
    assert nil_from_row({"nil_valuation": "$2.5M"}) == 2_500_000
