/**
 * CSC report normalization — keep athlete-card / client-preview figures from
 * ever being presented as final CSC recommendations.
 */
import type { AthleteRecord } from '../types/athlete'
import type {
  CscConfidenceRiskSection,
  CscDetailSection,
  CscExplanationSection,
  CscKeyValueDriver,
  CscReportComparablesRow,
  CscReportJson,
  CscReportMetadata,
  CscValidationSection,
  CscValueSection,
} from '../types/reports'
import { normalizeComparableRows } from './cscComparables'
import { fallbackTakeaway } from './cscDealCopy'
import { formatNilValue, formatScore } from './formatters'

/** Client-only scaffold used before / when the live CSC report is unavailable. */
export const CLIENT_PREVIEW_PRICING_METHOD = 'legacy_fallback'

export function isClientPreviewValuation(
  report: CscReportJson | null | undefined,
): boolean {
  return report?.value?.deal_pricing_method === CLIENT_PREVIEW_PRICING_METHOD
}

/** True only when the report carries API-backed valuation fields (not a client preview). */
export function hasFinalCscValuations(
  report: CscReportJson | null | undefined,
): boolean {
  if (!report?.value || isClientPreviewValuation(report)) return false
  const v = report.value
  return (
    v.activation_deal_mid != null ||
    v.annual_nil_benchmark != null ||
    v.total_benchmark != null ||
    (v.activation_deal_low != null && v.activation_deal_high != null)
  )
}

function withDefaultText(value: string | null | undefined, fallback: string) {
  const clean = (value ?? '').trim()
  return clean.length > 0 ? clean : fallback
}

function normalizeComparables(rows: CscReportComparablesRow[] | undefined): CscReportComparablesRow[] {
  return normalizeComparableRows(rows).slice(0, 12)
}

function levelFromScore(value: number | null | undefined, invert = false): 'High' | 'Moderate' | 'Low' {
  if (value == null || Number.isNaN(value)) return 'Moderate'
  const adjusted = invert ? 100 - value : value
  if (adjusted >= 66) return 'High'
  if (adjusted >= 40) return 'Moderate'
  return 'Low'
}

function buildFallbackDrivers(athlete: AthleteRecord | null | undefined): CscKeyValueDriver[] {
  return [
    {
      label: 'Brand Strength',
      signal: levelFromScore(athlete?.brand_score),
      explanation: `Brand score ${formatScore(athlete?.brand_score ?? null)} relative to peers.`,
    },
    {
      label: 'Market Proof',
      signal: levelFromScore(athlete?.proof_score),
      explanation: `Proof score ${formatScore(athlete?.proof_score ?? null)} with current verified activity.`,
    },
    {
      label: 'Exposure',
      signal: levelFromScore(athlete?.proximity_score),
      explanation: `Exposure score ${formatScore(athlete?.proximity_score ?? null)} for program/media visibility.`,
    },
    {
      label: 'Risk',
      signal: levelFromScore(athlete?.risk_score, true),
      explanation: `Risk score ${formatScore(athlete?.risk_score ?? null)} impacts valuation certainty.`,
    },
  ]
}

/**
 * Scaffold used only for narrative defaults when merging a live report.
 * Monetary recommendation fields stay null so athlete-card consensus is never
 * shown as a CSC suggested offer.
 */
export function buildClientPreviewReport(
  athlete: AthleteRecord | null | undefined,
  rows: CscReportComparablesRow[] = [],
): CscReportJson {
  const athleteName = athlete?.name
  const subject = athleteName ?? 'the selected athlete'
  const confidenceLevel = levelFromScore(
    athlete?.dollar_confidence?.dollar_confidence_score != null
      ? (athlete?.dollar_confidence?.dollar_confidence_score ?? 0) * 100
      : null,
  )
  const confidenceTag = `${confidenceLevel} Confidence`
  const riskLevel = levelFromScore(athlete?.risk_score ?? null, true)
  const drivers = buildFallbackDrivers(athlete)
  const marketValues = rows.map((r) => r.nil_valuation_consensus).filter((v): v is number => v != null)
  const marketLow = marketValues.length ? Math.min(...marketValues) : null
  const marketHigh = marketValues.length ? Math.max(...marketValues) : null
  const marketMedian = marketValues.length
    ? [...marketValues].sort((a, b) => a - b)[Math.floor(marketValues.length / 2)]
    : null

  return {
    value: {
      total_benchmark: null,
      range_low: null,
      range_high: null,
      annual_nil_benchmark: null,
      activation_deal_low: null,
      activation_deal_mid: null,
      activation_deal_high: null,
      season_partnership_low: null,
      season_partnership_high: null,
      deal_confidence: confidenceLevel,
      deal_uncertainty: null,
      deal_pricing_method: CLIENT_PREVIEW_PRICING_METHOD,
      deal_pricing_basis:
        'Client preview only — valuations are withheld until the full CSC report loads.',
      selected_deal_scope: 'standard_activation',
      deal_scopes: {
        standard_activation: {
          scope: 'standard_activation',
          label: 'Standard activation',
          low: null,
          mid: null,
          high: null,
          model_version: 'activation_prior_v2',
          calibrated: false,
          confidence: 'Uncalibrated',
          basis: 'Valuations withheld while the full report loads.',
          qualified_transactions: 0,
          validation_transactions: 0,
          empirical_coverage: null,
          target_coverage: null,
          median_absolute_percentage_error: null,
          evaluated_through: null,
          readiness: 'insufficient_data',
        },
      },
      tier_tag: 'Developing-tier',
      confidence_tag: confidenceTag,
      range_note: null,
      peer_range_applicable: true,
    },
    explanation: {
      executive_summary: fallbackTakeaway(subject, formatNilValue(null), formatNilValue(null), formatNilValue(null)),
      key_value_drivers: drivers,
      driver_takeaway: `${subject}'s offer is driven most by brand and exposure. Proof and risk decide how firmly you can hold the number.`,
    },
    validation: {
      market_context: `Peers at ${athlete?.conference ?? 'this conference'} ${athlete?.position ?? 'this position'}: yearly values from ${formatNilValue(marketLow)} to ${formatNilValue(marketHigh)} (median ${formatNilValue(marketMedian)}).`,
      comparable_tier: 'Athletes with a similar role and signal profile.',
      example_comparables: rows.slice(0, 5),
      takeaway: `Wait for the full CSC report before pricing a deal for ${subject}.`,
      comparable_state: rows.length >= 3 ? 'sufficient' : rows.length >= 1 ? 'sparse' : 'none',
      positional_reference_athletes: rows.length === 0 ? [] : [],
    },
    confidence_risk: {
      confidence_level: confidenceLevel,
      confidence_note: `${confidenceLevel} confidence from the signals and comps we have so far.`,
      risk_level: riskLevel,
      risk_note: `${riskLevel} risk from roster status and modeled risk posture.`,
    },
    detail: {
      shap_attribution: 'SHAP attribution pending latest explainable model output.',
      methodology: 'Comparable-weighted NIL banding with Gravity score components and verified market observations.',
      inputs: 'Inputs include sport, position, comparables set, confidence threshold, and current score components.',
    },
    metadata: {
      tier_version: 'tier_v1',
      tier_v1: 'Developing',
      tier_v2: 'Developing',
      cohort_window_days_used: 21,
      season_state: 'unknown',
      cohort_size: rows.length,
      cohort_fallback_step: 3,
      comparable_state: rows.length >= 3 ? 'sufficient' : rows.length >= 1 ? 'sparse' : 'none',
      comparable_sets_computed_at: null,
      exposure_formula_version: 'exposure_formula_v1',
      exposure_formula_weights: { proximity_weight: 0.6, velocity_weight: 0.4 },
      rollout_phase: 'phase1',
      low_cohort_data: true,
      athlete_benchmark_percentile_in_cohort: null,
    },
    executive_summary: '',
    gravity_score_table: '',
    comparables_analysis: rows,
    nil_range_note: '',
    shap_narrative: '',
    risk_assessment: '',
    methodology: '',
  }
}

/**
 * Merge a live API report with narrative defaults.
 * Does not fill monetary recommendation fields from athlete-card consensus.
 */
export function normalizeCscReport(
  report: CscReportJson | null | undefined,
  athlete: AthleteRecord | null | undefined,
): CscReportJson {
  const legacyRows = normalizeComparables(report?.comparables_analysis)
  const preview = buildClientPreviewReport(athlete, legacyRows)
  if (!report) return preview

  const legacyExec = withDefaultText(report.executive_summary, preview.explanation.executive_summary)
  const legacyMethod = withDefaultText(report.methodology, preview.detail.methodology)
  const legacyShap = withDefaultText(report.shap_narrative, preview.detail.shap_attribution)
  const legacyRisk = withDefaultText(report.risk_assessment, preview.confidence_risk.risk_note)

  // Money: API fields only. Never coalesce to athlete-card / preview dollars.
  const value: CscValueSection = {
    total_benchmark: report.value?.total_benchmark ?? null,
    range_low: report.value?.range_low ?? null,
    range_high: report.value?.range_high ?? null,
    annual_nil_benchmark: report.value?.annual_nil_benchmark ?? report.value?.total_benchmark ?? null,
    activation_deal_low: report.value?.activation_deal_low ?? report.value?.range_low ?? null,
    activation_deal_mid:
      report.value?.activation_deal_mid ??
      (report.value?.range_low != null && report.value?.range_high != null
        ? (report.value.range_low + report.value.range_high) / 2
        : null),
    activation_deal_high: report.value?.activation_deal_high ?? report.value?.range_high ?? null,
    season_partnership_low: report.value?.season_partnership_low ?? null,
    season_partnership_high: report.value?.season_partnership_high ?? null,
    deal_confidence: report.value?.deal_confidence ?? null,
    deal_uncertainty: report.value?.deal_uncertainty ?? null,
    deal_pricing_method: report.value?.deal_pricing_method ?? null,
    deal_pricing_basis: report.value?.deal_pricing_basis ?? null,
    selected_deal_scope: report.value?.selected_deal_scope,
    deal_scopes: report.value?.deal_scopes,
    tier_tag: report.value?.tier_tag ?? preview.value.tier_tag,
    confidence_tag: report.value?.confidence_tag ?? preview.value.confidence_tag,
    range_note: report.value?.range_note ?? null,
    peer_range_applicable: report.value?.peer_range_applicable ?? true,
  }

  const explanation: CscExplanationSection = {
    executive_summary: withDefaultText(report.explanation?.executive_summary, legacyExec),
    key_value_drivers: report.explanation?.key_value_drivers?.length
      ? report.explanation.key_value_drivers
      : preview.explanation.key_value_drivers,
    driver_takeaway: withDefaultText(
      report.explanation?.driver_takeaway,
      preview.explanation.driver_takeaway,
    ),
  }

  const validationRows = report.validation?.example_comparables?.length
    ? normalizeComparables(report.validation.example_comparables)
    : legacyRows.length
      ? legacyRows
      : preview.validation.example_comparables

  const validation: CscValidationSection = {
    market_context: withDefaultText(report.validation?.market_context, preview.validation.market_context),
    comparable_tier: withDefaultText(report.validation?.comparable_tier, preview.validation.comparable_tier),
    example_comparables: validationRows,
    takeaway: withDefaultText(report.validation?.takeaway, preview.validation.takeaway),
    comparable_state: report.validation?.comparable_state ?? preview.validation.comparable_state,
    positional_reference_athletes:
      report.validation?.positional_reference_athletes ?? preview.validation.positional_reference_athletes,
  }

  const confidenceRisk: CscConfidenceRiskSection = {
    confidence_level: report.confidence_risk?.confidence_level ?? preview.confidence_risk.confidence_level,
    confidence_note: withDefaultText(
      report.confidence_risk?.confidence_note,
      preview.confidence_risk.confidence_note,
    ),
    risk_level: report.confidence_risk?.risk_level ?? preview.confidence_risk.risk_level,
    risk_note: withDefaultText(report.confidence_risk?.risk_note, legacyRisk),
  }

  const detail: CscDetailSection = {
    shap_attribution: withDefaultText(report.detail?.shap_attribution, legacyShap),
    methodology: withDefaultText(report.detail?.methodology, legacyMethod),
    inputs: withDefaultText(report.detail?.inputs, preview.detail.inputs),
    blocks: report.detail?.blocks ?? undefined,
  }

  const metadata: CscReportMetadata = {
    tier_version: report.metadata?.tier_version ?? preview.metadata.tier_version,
    tier_v1: report.metadata?.tier_v1 ?? preview.metadata.tier_v1,
    tier_v2: report.metadata?.tier_v2 ?? preview.metadata.tier_v2,
    cohort_window_days_used: report.metadata?.cohort_window_days_used ?? preview.metadata.cohort_window_days_used,
    season_state: report.metadata?.season_state ?? preview.metadata.season_state,
    cohort_size: report.metadata?.cohort_size ?? preview.metadata.cohort_size,
    cohort_fallback_step: report.metadata?.cohort_fallback_step ?? preview.metadata.cohort_fallback_step,
    comparable_state: report.metadata?.comparable_state ?? preview.metadata.comparable_state,
    comparable_sets_computed_at: report.metadata?.comparable_sets_computed_at ?? null,
    exposure_formula_version: report.metadata?.exposure_formula_version ?? preview.metadata.exposure_formula_version,
    exposure_formula_weights: report.metadata?.exposure_formula_weights ?? preview.metadata.exposure_formula_weights,
    rollout_phase: report.metadata?.rollout_phase ?? preview.metadata.rollout_phase,
    low_cohort_data: report.metadata?.low_cohort_data ?? preview.metadata.low_cohort_data,
    athlete_benchmark_percentile_in_cohort:
      report.metadata?.athlete_benchmark_percentile_in_cohort ??
      preview.metadata.athlete_benchmark_percentile_in_cohort,
    selected_deal_scope: report.metadata?.selected_deal_scope,
    deal_scope_calibrated: report.metadata?.deal_scope_calibrated,
    deal_scope_readiness: report.metadata?.deal_scope_readiness,
    model_status: report.metadata?.model_status,
    model_version: report.metadata?.model_version,
    roster_verification_status: report.metadata?.roster_verification_status,
    roster_freshness_warning: report.metadata?.roster_freshness_warning,
    conference_tier: report.metadata?.conference_tier,
    cohort_fit: report.metadata?.cohort_fit,
    report_id: report.metadata?.report_id,
  }

  return {
    value,
    explanation,
    validation,
    confidence_risk: confidenceRisk,
    detail,
    metadata,
    executive_summary: report.executive_summary,
    gravity_score_table: report.gravity_score_table,
    comparables_analysis: report.comparables_analysis,
    nil_range_note: report.nil_range_note,
    shap_narrative: report.shap_narrative,
    risk_assessment: report.risk_assessment,
    methodology: report.methodology,
  }
}
