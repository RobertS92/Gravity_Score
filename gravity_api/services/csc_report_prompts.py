"""Prompts used by the CSC report LLM prose module.

These prompts are intentionally explicit about the four content surfaces:

  1. EXECUTIVE_SUMMARY_PROMPT  – 4–6 sentence narrative for Section 2a.
  2. DRIVER_PROMPT             – 2–3 sentences per key value driver Interpretation
                                 (evidence + peer meaning + actionability).
  3. VALUE_INTERPRETATION_PROMPT – Validation takeaway (Section 3c).
  4. CONFIDENCE_RATIONALE_PROMPT / RISK_RATIONALE_PROMPT
                                – One-line `confidence_note` / `risk_note`.

Each prompt has explicit forbidden terms and length guidance so the LLM
service can validate output deterministically before accepting it. The
prompts are private (model-facing) and never displayed to users.
"""

from __future__ import annotations

# Terms that must never appear in user-facing prose. Acceptance tests pin
# this list against the validator.
FORBIDDEN_PROSE_TERMS: tuple[str, ...] = (
    "BPXVR",
    "composite_fallback",
    "heuristic_fallback",
    "0.6*proximity",
    "0.4*velocity",
    "shap",
    "ml_sync",
    "{",
    "}",
)


EXECUTIVE_SUMMARY_PROMPT = """\
You write the 2026 Gravity Score CSC athlete valuation report Executive Summary.

Audience: athletic department GM / collective ops lead. Your prose must be
specific to this athlete and avoid generic disclaimers. Reference the
benchmark, the recommended deal range (which brackets the benchmark), the
cohort positioning, and the single strongest driver. When confidence is not
High, surface the primary uncertainty in one sentence.

Hard constraints — output must satisfy ALL of these:
  - 4 to 6 sentences, no bullets, no headings.
  - Use the athlete's name at least once.
  - Format dollar values with the unit already used in `benchmark_text`.
  - Call the band a "recommended deal range" (not a peer market range).
  - DO NOT mention the internal model name, the exposure formula constants,
    SHAP values, raw component scores, or any number with a decimal in the
    range 0.0–9.9.
  - DO NOT mention model versions, fallback scorers, or system internals.
  - DO NOT use the words 'BPXVR', 'composite_fallback', or 'heuristic'.

Inputs (JSON):
{inputs_json}

Return only the prose. No JSON. No preamble."""


DRIVER_PROMPT = """\
You write the Interpretation paragraph for a single Key Value Driver row in the
Gravity Score CSC report. Match the quality of an expert NIL analyst brief —
specific, evidence-backed, and actionable for athletic department / collective ops.

Driver: {driver_label}
Signal: {signal_level}
Athlete: {athlete_name}
Position: {position_group}
Cohort: {cohort_label}
Evidence bundle: {evidence_summary}

Write 2 to 3 sentences that cover ALL of the following beats:
  1. Evidence — synthesize the strongest available signals for {athlete_name}
     for THIS driver. For Brand Strength include family/name heritage when
     present, owned social, earned demand, and school/conference context.
     For Exposure use news/search/Wikipedia/proximity. For Market Proof use
     verified deals and comps context. For Momentum use velocity and 30-day
     trajectories. For Commercial Readiness use reach/engagement/deal history/
     roster status. For Risk use roster status and modeled risk posture.
     Never reduce the driver to a generic peer-rank line. If platforms or
     fields are unavailable, say so.
  2. Peer meaning / key insight — what the mix means commercially (e.g. concentrated
     owned audience vs diversified brand equity) and how it positions the athlete
     in the {cohort_label} market at a {signal_level} signal.
  3. Actionability — why this matters for deal construction (campaign types,
     timing, contract posture, or partnership fit), tailored to the signal mix.

Hard constraints — output must satisfy ALL of these:
  - 2 to 4 sentences. No bullets, no headings.
  - Use {athlete_name} at least once.
  - DO NOT cite raw decimal component scores (e.g. 81.2). Prefer whole-number
    follower counts ("750K", "1 million") or qualitative engagement language.
  - DO NOT mention SHAP, BPXVR, exposure formulas, or any system internals.
  - Avoid hedge phrases ('it appears that', 'we believe', 'might be').
  - Do not write a generic peer-only line like "Brand Strength leads the cohort."
  - Do not imply the brand is Instagram-only when news, search, Wikipedia,
    school, or conference context is present in the evidence bundle.

Return only the prose."""


VALUE_INTERPRETATION_PROMPT = """\
You write the Validation section takeaway (Section 3c) of the Gravity Score CSC report.

This sentence references both Market Context AND Comparable Athletes for
{athlete_name}.

Cohort summary: {market_context}
Comparable summary: {comparables_summary}
Athlete benchmark: {benchmark_text}
Athlete percentile in cohort: {percentile_text}

Hard constraints:
  - 1 to 2 sentences.
  - Must reference both the cohort and the comparables.
  - Use {athlete_name} or a pronoun bound to him.
  - DO NOT mention SHAP, BPXVR, raw component scores, or system internals.

Return only the prose."""


CONFIDENCE_RATIONALE_PROMPT = """\
You write the one-line confidence_note for a Gravity Score CSC report.

Confidence level: {confidence_level}
Causes (in priority order): {causes}
Athlete: {athlete_name}

Hard constraints:
  - One sentence, max 25 words.
  - Lead with the confidence level (e.g. 'Moderate confidence:').
  - Cite the strongest cause from `causes` only — do not list multiple.
  - DO NOT cite raw scores or system internals.

Return only the prose."""


RISK_RATIONALE_PROMPT = """\
You write the one-line risk_note for a Gravity Score CSC report.

Risk level: {risk_level}
Athlete: {athlete_name}
Position: {position_group}
Notable risk factors: {risk_factors}

Hard constraints:
  - One sentence, max 25 words.
  - Lead with the risk level (e.g. 'Low risk:').
  - Cite at most one risk factor.
  - DO NOT cite raw scores or system internals.

Return only the prose."""


ALL_PROMPTS: dict[str, str] = {
    "executive_summary": EXECUTIVE_SUMMARY_PROMPT,
    "driver": DRIVER_PROMPT,
    "value_interpretation": VALUE_INTERPRETATION_PROMPT,
    "confidence_rationale": CONFIDENCE_RATIONALE_PROMPT,
    "risk_rationale": RISK_RATIONALE_PROMPT,
}


def get_prompt(name: str) -> str:
    """Return the prompt template by name; raises KeyError on unknown surface."""
    return ALL_PROMPTS[name]
