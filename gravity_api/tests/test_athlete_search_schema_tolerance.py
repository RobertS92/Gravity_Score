import asyncio
from unittest.mock import AsyncMock

from gravity_api.services.athlete_search import _with_impact_aliases, search_athletes


def test_search_does_not_require_optional_nil_valuation_column():
    conn = AsyncMock()
    conn.fetch.return_value = []
    conn.fetchval.return_value = 0

    result = asyncio.run(search_athletes(conn, limit=10, offset=0))

    assert result == {"athletes": [], "total": 0, "returned": 0}
    search_sql = conn.fetch.await_args.args[0]
    assert "a.nil_valuation_raw" not in search_sql
    assert "to_jsonb(a) -> 'nil_valuation_raw'" in search_sql


def test_search_rows_expose_impact_score_aliases():
    out = _with_impact_aliases(
        {
            "name": "Patrick Mahomes",
            "value_score": 88.9295,
            "value_sport_percentile": 97.6,
            "value_score_source": "win_impact_v1_additive",
        }
    )
    assert out["impact_score"] == 88.9295
    assert out["impact_sport_percentile"] == 97.6
    assert out["impact_score_source"] == "win_impact_v1_additive"
