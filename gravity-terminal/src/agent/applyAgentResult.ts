import type { NavigateFunction } from 'react-router-dom'
import type { CscReportJson } from '../types/reports'
import { useAthleteStore } from '../stores/athleteStore'
import { useUiStore } from '../stores/uiStore'

function isCscReport(o: unknown): o is CscReportJson {
  if (!o || typeof o !== 'object') return false
  const x = o as Record<string, unknown>
  return (
    (typeof x.executive_summary === 'string' && typeof x.gravity_score_table === 'string') ||
    (typeof x.value === 'object' && typeof x.explanation === 'object')
  )
}

function normalizeCscReport(o: CscReportJson): CscReportJson {
  const legacyComparables = Array.isArray(o.comparables_analysis) ? o.comparables_analysis : []
  return {
    value: {
      total_benchmark: o.value?.total_benchmark ?? null,
      range_low: o.value?.range_low ?? null,
      range_high: o.value?.range_high ?? null,
      tier_tag: o.value?.tier_tag ?? null,
      confidence_tag: o.value?.confidence_tag ?? null,
    },
    explanation: {
      executive_summary: o.explanation?.executive_summary ?? o.executive_summary ?? '',
      key_value_drivers: o.explanation?.key_value_drivers ?? [],
      driver_takeaway: o.explanation?.driver_takeaway ?? '',
    },
    validation: {
      market_context: o.validation?.market_context ?? '',
      comparable_tier: o.validation?.comparable_tier ?? '',
      example_comparables: o.validation?.example_comparables ?? legacyComparables,
      takeaway: o.validation?.takeaway ?? '',
      comparable_state: o.validation?.comparable_state ?? 'none',
      positional_reference_athletes: o.validation?.positional_reference_athletes ?? [],
    },
    confidence_risk: {
      confidence_level: o.confidence_risk?.confidence_level ?? 'Moderate',
      confidence_note: o.confidence_risk?.confidence_note ?? '',
      risk_level: o.confidence_risk?.risk_level ?? 'Moderate',
      risk_note: o.confidence_risk?.risk_note ?? o.risk_assessment ?? '',
    },
    detail: {
      shap_attribution: o.detail?.shap_attribution ?? o.shap_narrative ?? '',
      methodology: o.detail?.methodology ?? o.methodology ?? '',
      inputs: o.detail?.inputs ?? '',
    },
    metadata: {
      tier_version: o.metadata?.tier_version ?? 'tier_v1',
      tier_v1: o.metadata?.tier_v1 ?? 'Developing',
      tier_v2: o.metadata?.tier_v2 ?? 'Developing',
      cohort_window_days_used: o.metadata?.cohort_window_days_used ?? 21,
      season_state: o.metadata?.season_state ?? 'unknown',
      cohort_size: o.metadata?.cohort_size ?? 0,
      cohort_fallback_step: o.metadata?.cohort_fallback_step ?? 3,
      comparable_state: o.metadata?.comparable_state ?? 'none',
      comparable_sets_computed_at: o.metadata?.comparable_sets_computed_at ?? null,
      exposure_formula_version: o.metadata?.exposure_formula_version ?? 'exposure_formula_v1',
      exposure_formula_weights: o.metadata?.exposure_formula_weights ?? { proximity_weight: 0.6, velocity_weight: 0.4 },
      rollout_phase: o.metadata?.rollout_phase ?? 'phase1',
      low_cohort_data: o.metadata?.low_cohort_data ?? true,
      athlete_benchmark_percentile_in_cohort: o.metadata?.athlete_benchmark_percentile_in_cohort ?? null,
    },
    executive_summary: o.executive_summary,
    gravity_score_table: o.gravity_score_table,
    comparables_analysis: legacyComparables,
    nil_range_note: o.nil_range_note,
    shap_narrative: o.shap_narrative,
    risk_assessment: o.risk_assessment,
    methodology: o.methodology,
  }
}

function extractJsonObject(text: string): string | null {
  const t = text.trim()
  const codeBlock = t.match(/```(?:json)?\s*([\s\S]*?)```/i)
  if (codeBlock) {
    const inner = codeBlock[1]?.trim()
    if (inner?.startsWith('{')) return inner
  }
  const i = t.indexOf('{')
  if (i < 0) return null
  let depth = 0
  for (let j = i; j < t.length; j++) {
    const c = t[j]
    if (c === '{') depth++
    else if (c === '}') {
      depth--
      if (depth === 0) return t.slice(i, j + 1)
    }
  }
  return null
}

/**
 * If the model returned JSON for a CSC report or athlete id / profile, apply it and navigate.
 * Returns true when navigation was triggered (response may still be shown in the output panel).
 */
export async function tryApplyAgentResponseText(text: string, navigate: NavigateFunction): Promise<boolean> {
  const blob = extractJsonObject(text)
  if (!blob) return false
  let o: unknown
  try {
    o = JSON.parse(blob)
  } catch {
    return false
  }
  if (isCscReport(o)) {
    useUiStore.getState().setCscLockedFromAgent(true)
    navigate('/csc', { state: { agentCscReport: normalizeCscReport(o) } })
    return true
  }
  if (typeof o === 'object' && o !== null && 'athlete_id' in o) {
    const aid = String((o as { athlete_id: unknown }).athlete_id).trim()
    if (aid) {
      await useAthleteStore.getState().setActiveAthlete(aid)
      navigate('/')
      return true
    }
  }
  return false
}
