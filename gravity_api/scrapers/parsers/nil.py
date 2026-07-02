"""NIL valuation parsing and verification."""

from __future__ import annotations

from typing import Any

from gravity_api.scrapers.parsers.common import parse_money_usd

SUSPECT_BAND_LO = 5_000
SUSPECT_BAND_HI = 500_000


def parse_nil_deals_from_text(text: str) -> list[dict[str, Any]]:
    """Extract individual NIL deal mentions from On3 / news markdown."""
    import re

    deals: list[dict[str, Any]] = []
    seen: set[str] = set()
    for m in re.finditer(
        r"(?:deal|partnership|agreement)[^\n]{0,80}?(\$[\d,.]+[KMB]?)",
        text,
        re.I,
    ):
        amt = parse_money_usd(m.group(1))
        if not amt or amt < 100:
            continue
        key = f"{amt:.0f}"
        if key in seen:
            continue
        seen.add(key)
        deals.append({"amount_usd": amt, "source": "on3_parse"})
    return deals[:20]


def parse_nil_from_text(text: str) -> float | None:
    for pat in (
        r"nil valuation[^\d$]*(\$[\d,.]+[KMB]?)",
        r"valued at[^\d$]*(\$[\d,.]+[KMB]?)",
        r"(\$[\d,.]+[KMB]?)\s+nil",
    ):
        import re

        m = re.search(pat, text, re.I)
        if m:
            val = parse_money_usd(m.group(1))
            if val:
                return val
    return None


def is_suspect_nil(val: float | None) -> bool:
    if val is None:
        return False
    return SUSPECT_BAND_LO <= val <= SUSPECT_BAND_HI


def verify_nil_consensus(sources: list[dict[str, Any]]) -> dict[str, Any]:
    """Cross-source NIL consensus from On3, Opendorse, news events."""
    valuations: list[tuple[float, float, str]] = []
    deal_count = 0
    last_deal_date = None
    for src in sources:
        v = src.get("nil_valuation")
        if v is not None:
            try:
                fv = float(v)
            except (TypeError, ValueError):
                continue
            conf = float(src.get("confidence") or 0.7)
            if is_suspect_nil(fv) and conf < 0.9:
                fv *= 1000.0
            valuations.append((fv, conf, str(src.get("source") or "unknown")))
        deal_count += int(src.get("nil_deal_count") or 0)
        if src.get("nil_last_deal_date"):
            last_deal_date = src.get("nil_last_deal_date")

    if not valuations:
        return {
            "nil_confidence": 0.0,
            "nil_deal_count_verified": deal_count,
        }

    total_w = sum(w for _, w, _ in valuations)
    p50 = sum(v * w for v, w, _ in valuations) / total_w if total_w else valuations[0][0]
    best_source = max(valuations, key=lambda x: x[1])[2]
    confidence = min(0.98, total_w / len(valuations))

    return {
        "nil_valuation": round(p50, 2),
        "nil_valuation_source": best_source,
        "nil_deal_count_verified": deal_count,
        "nil_last_deal_date": last_deal_date,
        "nil_confidence": round(confidence, 3),
    }
