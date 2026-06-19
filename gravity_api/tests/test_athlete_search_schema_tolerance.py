import asyncio
from unittest.mock import AsyncMock

from gravity_api.services.athlete_search import search_athletes


def test_search_does_not_require_optional_nil_valuation_column():
    conn = AsyncMock()
    conn.fetch.return_value = []
    conn.fetchval.return_value = 0

    result = asyncio.run(search_athletes(conn, limit=10, offset=0))

    assert result == {"athletes": [], "total": 0, "returned": 0}
    search_sql = conn.fetch.await_args.args[0]
    assert "a.nil_valuation_raw" not in search_sql
    assert "to_jsonb(a) -> 'nil_valuation_raw'" in search_sql
