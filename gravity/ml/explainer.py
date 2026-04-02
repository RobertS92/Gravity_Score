"""LLM explanation layer (Claude / Anthropic) from scores + SHAP drivers."""

from __future__ import annotations

import os
from typing import Any

from gravity.ml.shap_scorer import ComponentName


def _template_summary(
    name: str,
    sport: str,
    team: str,
    gravity: float,
    components: dict[ComponentName, float],
    brand_drivers: list[str],
    proof_drivers: list[str],
    proximity_drivers: list[str],
    velocity_drivers: list[str],
    risk_drivers: list[str],
) -> str:
    return (
        f"{name} ({team}, {sport}) posts a Gravity Score of {gravity:.1f}/100. "
        f"Brand ({components['brand']:.1f}) and Proof ({components['proof']:.1f}) "
        f"are the strongest pillars in this breakdown, shaped mainly by "
        f"{', '.join(brand_drivers[:2])} versus on-field signals such as {', '.join(proof_drivers[:2])}. "
        f"Proximity sits at {components['proximity']:.1f}, velocity at {components['velocity']:.1f}, "
        f"and risk at {components['risk']:.1f}—monitor {', '.join(risk_drivers[:2]) or 'injury/transfer context'} "
        f"for underwriting or contract timing."
    )


def generate_gravity_explanation(
    *,
    athlete_name: str,
    sport: str,
    team: str,
    gravity_score: float,
    components: dict[ComponentName, float],
    top_features_by_component: dict[ComponentName, list[str]],
    model: str = "claude-sonnet-4-20250514",
) -> str:
    """
    Call Anthropic Messages API when ANTHROPIC_API_KEY is set; otherwise template fallback.
    """
    def _drivers(c: ComponentName) -> list[str]:
        return top_features_by_component.get(c, [])[:2]

    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        return _template_summary(
            athlete_name,
            sport,
            team,
            gravity_score,
            components,
            _drivers("brand"),
            _drivers("proof"),
            _drivers("proximity"),
            _drivers("velocity"),
            _drivers("risk"),
        )

    try:
        import anthropic
    except ImportError:
        return _template_summary(
            athlete_name,
            sport,
            team,
            gravity_score,
            components,
            _drivers("brand"),
            _drivers("proof"),
            _drivers("proximity"),
            _drivers("velocity"),
            _drivers("risk"),
        )

    client = anthropic.Anthropic(api_key=key)
    prompt = f"""Given this athlete's Gravity Score breakdown:
- Name: {athlete_name}, Sport: {sport}, Team: {team}
- Gravity Score (model): {gravity_score:.1f}/100
- Brand: {components['brand']:.1f} (driven by: {_drivers('brand')})
- Proof: {components['proof']:.1f} (driven by: {_drivers('proof')})
- Proximity: {components['proximity']:.1f} (driven by: {_drivers('proximity')})
- Velocity: {components['velocity']:.1f} (driven by: {_drivers('velocity')})
- Risk: {components['risk']:.1f} (driven by: {_drivers('risk')})

Write a 3-sentence executive summary explaining why this athlete scored near {gravity_score:.1f}/100 and what their primary commercial value drivers are.
Do not make up information not in the data above."""

    msg = client.messages.create(
        model=model,
        max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    block = msg.content[0]
    if hasattr(block, "text"):
        return str(block.text)
    return str(block)


__all__ = ["generate_gravity_explanation"]
