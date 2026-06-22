"""Brand taxonomy loader and athlete partnership scoring."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

_CONFIG = Path(__file__).resolve().parents[2] / "config" / "brand_taxonomy.json"


@dataclass(frozen=True)
class BrandEntry:
    key: str
    category: str
    names: tuple[str, ...]
    prestige: float
    tier: str
    component: str  # brand | proof
    proof_boost: float = 0.0


@dataclass
class BrandMatch:
    brand_key: str
    brand_name: str
    category: str
    prestige: float
    component: str
    proof_boost: float
    deal_value: float | None = None
    verified: bool = False


@dataclass
class PartnershipScoreResult:
    partnership_brand_score: float
    partnership_proof_boost: float
    deal_count: int
    verified_deal_count: int
    category_scores: dict[str, float] = field(default_factory=dict)
    matches: list[BrandMatch] = field(default_factory=list)
    top_brands: list[dict[str, Any]] = field(default_factory=list)


class BrandTaxonomy:
    def __init__(self, data: dict[str, Any]) -> None:
        self.schema_version = data.get("schema_version", "brand_taxonomy_v1")
        self._entries: list[BrandEntry] = []
        self._name_index: dict[str, BrandEntry] = {}
        for cat_key, block in (data.get("categories") or {}).items():
            component = str(block.get("component", "brand"))
            for b in block.get("brands") or []:
                entry = BrandEntry(
                    key=str(b["key"]),
                    category=cat_key,
                    names=tuple(str(n).lower() for n in b.get("names") or []),
                    prestige=float(b.get("prestige", 50)),
                    tier=str(b.get("tier", "national")),
                    component=component,
                    proof_boost=float(b.get("proof_boost", 0.0)),
                )
                self._entries.append(entry)
                for name in entry.names:
                    self._name_index[name] = entry

    @property
    def entries(self) -> list[BrandEntry]:
        return list(self._entries)

    def categories(self) -> list[str]:
        return sorted({e.category for e in self._entries})

    def list_by_category(self, category: str) -> list[BrandEntry]:
        return [e for e in self._entries if e.category == category]

    def match_brand(self, name: str) -> BrandEntry | None:
        if not name:
            return None
        normalized = _normalize(name)
        if normalized in self._name_index:
            return self._name_index[normalized]
        for entry in self._entries:
            for alias in entry.names:
                if alias in normalized or normalized in alias:
                    return entry
        return None


def _normalize(text: str) -> str:
    t = text.strip().lower()
    t = re.sub(r"[^\w\s&'-]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _extract_deals(raw: dict[str, Any]) -> list[dict[str, Any]]:
    deals: list[dict[str, Any]] = []
    for key in ("nil_deals", "brand_deals", "deals", "sponsorships"):
        block = raw.get(key)
        if isinstance(block, list):
            deals.extend(block)
    if raw.get("brand_name"):
        deals.append(
            {
                "brand": raw["brand_name"],
                "value": raw.get("deal_value"),
                "verified": raw.get("deal_verified", False),
            }
        )
    return deals


def _deal_brand_name(deal: dict[str, Any]) -> str:
    for k in ("brand", "brand_name", "sponsor", "company", "name"):
        if deal.get(k):
            return str(deal[k])
    return ""


@lru_cache(maxsize=1)
def get_taxonomy() -> BrandTaxonomy:
    if not _CONFIG.exists():
        return BrandTaxonomy({"categories": {}})
    return BrandTaxonomy(json.loads(_CONFIG.read_text(encoding="utf-8")))


def score_athlete_partnerships(raw: dict[str, Any]) -> PartnershipScoreResult:
    """Score known brand partnerships; returns brand score + proof boost."""
    taxonomy = get_taxonomy()
    deals = _extract_deals(raw)
    matches: list[BrandMatch] = []
    category_prestige: dict[str, list[float]] = {}
    proof_boosts: list[float] = []

    for deal in deals:
        brand_name = _deal_brand_name(deal)
        if not brand_name:
            continue
        entry = taxonomy.match_brand(brand_name)
        if not entry:
            continue
        deal_val = deal.get("value") or deal.get("deal_value")
        try:
            deal_val_f = float(deal_val) if deal_val is not None else None
        except (TypeError, ValueError):
            deal_val_f = None
        verified = bool(deal.get("verified") or deal.get("is_verified"))
        weight = 1.0 + (0.25 if verified else 0.0) + (0.15 if deal_val_f and deal_val_f > 50_000 else 0.0)
        prestige = entry.prestige * weight
        matches.append(
            BrandMatch(
                brand_key=entry.key,
                brand_name=brand_name,
                category=entry.category,
                prestige=min(100.0, prestige),
                component=entry.component,
                proof_boost=entry.proof_boost,
                deal_value=deal_val_f,
                verified=verified,
            )
        )
        category_prestige.setdefault(entry.category, []).append(min(100.0, prestige))
        if entry.proof_boost > 0:
            proof_boosts.append(entry.proof_boost * (1.2 if verified else 1.0))

    if not matches:
        return PartnershipScoreResult(
            partnership_brand_score=0.0,
            partnership_proof_boost=0.0,
            deal_count=len(deals),
            verified_deal_count=0,
        )

    # Top-weighted brand partnerships (diminishing returns after 5)
    sorted_matches = sorted(matches, key=lambda m: m.prestige, reverse=True)
    weights = [1.0, 0.85, 0.7, 0.55, 0.45, 0.35, 0.25, 0.2]
    brand_scores: list[float] = []
    for i, m in enumerate(sorted_matches[:8]):
        if m.component == "brand":
            brand_scores.append(m.prestige * weights[min(i, len(weights) - 1)])

    partnership_brand = sum(brand_scores) / len(brand_scores) if brand_scores else 0.0
    partnership_brand = min(100.0, partnership_brand * (1.0 + 0.05 * min(len(brand_scores), 4)))

    category_avg = {
        cat: sum(vals) / len(vals) for cat, vals in category_prestige.items()
    }
    proof_boost = min(25.0, sum(proof_boosts) * 8.0) if proof_boosts else 0.0

    top_brands = [
        {
            "brand_key": m.brand_key,
            "brand_name": m.brand_name,
            "category": m.category,
            "prestige": round(m.prestige, 2),
            "component": m.component,
            "verified": m.verified,
        }
        for m in sorted_matches[:10]
    ]

    return PartnershipScoreResult(
        partnership_brand_score=round(partnership_brand, 2),
        partnership_proof_boost=round(proof_boost, 2),
        deal_count=len(deals),
        verified_deal_count=sum(1 for m in matches if m.verified),
        category_scores={k: round(v, 2) for k, v in category_avg.items()},
        matches=matches,
        top_brands=top_brands,
    )


def enrich_raw_with_partnerships(raw: dict[str, Any]) -> dict[str, Any]:
    """Add partnership fields to raw_data for ML and feature engineering."""
    result = score_athlete_partnerships(raw)
    out = dict(raw)
    out["partnership_brand_score"] = result.partnership_brand_score
    out["partnership_proof_boost"] = result.partnership_proof_boost
    out["partnership_deal_count"] = result.deal_count
    out["partnership_verified_count"] = result.verified_deal_count
    out["partnership_category_scores"] = result.category_scores
    out["partnership_top_brands"] = result.top_brands
    return out


def blend_brand_with_partnerships(social_brand: float, partnership_score: float) -> float:
    """Blend social-derived brand with partnership prestige."""
    if partnership_score <= 0:
        return social_brand
    if social_brand <= 0:
        return partnership_score
    # Partnerships lift brand meaningfully but don't fully replace reach
    return min(100.0, 0.62 * social_brand + 0.38 * partnership_score)


def apply_proof_partnership_boost(proof: float, boost: float) -> float:
    if boost <= 0:
        return proof
    return min(100.0, proof + boost * 0.35)
