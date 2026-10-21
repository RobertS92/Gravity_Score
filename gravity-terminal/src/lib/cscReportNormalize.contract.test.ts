import { describe, expect, it } from 'vitest'
import type { AthleteRecord } from '../types/athlete'
import type { CscReportJson } from '../types/reports'
import {
  CLIENT_PREVIEW_PRICING_METHOD,
  buildClientPreviewReport,
  hasFinalCscValuations,
  isClientPreviewValuation,
  normalizeCscReport,
} from './cscReportNormalize'

const athlete = {
  athlete_id: 'a1',
  name: 'Test Athlete',
  sport: 'CFB',
  nil_valuation_consensus: 156_000,
  dollar_p50_usd: 156_000,
  nil_range_low: 100_000,
  nil_range_high: 200_000,
  brand_score: 70,
  proof_score: 65,
  proximity_score: 60,
  risk_score: 20,
} as AthleteRecord

function liveReport(overrides?: Partial<CscReportJson['value']>): CscReportJson {
  return {
    value: {
      total_benchmark: 3_700_000,
      range_low: 40_000,
      range_high: 70_000,
      annual_nil_benchmark: 3_700_000,
      activation_deal_low: 40_000,
      activation_deal_mid: 54_000,
      activation_deal_high: 70_000,
      deal_pricing_method: 'deal_pricing_v2',
      tier_tag: 'High-tier',
      confidence_tag: 'High Confidence',
      ...overrides,
    },
    explanation: {
      executive_summary: 'Live summary',
      key_value_drivers: [],
      driver_takeaway: 'Live takeaway',
    },
    validation: {
      market_context: 'ctx',
      comparable_tier: 'tier',
      example_comparables: [],
      takeaway: 'takeaway',
      comparable_state: 'sufficient',
      positional_reference_athletes: [],
    },
    confidence_risk: {
      confidence_level: 'High',
      confidence_note: 'note',
      risk_level: 'Low',
      risk_note: 'risk',
    },
    detail: {
      shap_attribution: 'shap',
      methodology: 'method',
      inputs: 'inputs',
    },
    metadata: {
      tier_version: 'tier_v1',
      tier_v1: 'High',
      tier_v2: 'High',
      cohort_window_days_used: 21,
      season_state: 'in_season',
      cohort_size: 12,
      cohort_fallback_step: 0,
      comparable_state: 'sufficient',
      exposure_formula_version: 'exposure_formula_v1',
      exposure_formula_weights: { proximity_weight: 0.6, velocity_weight: 0.4 },
      rollout_phase: 'phase1',
      low_cohort_data: false,
      model_status: 'production',
    },
  }
}

describe('client preview valuations', () => {
  it('never fills money from athlete-card consensus', () => {
    const preview = buildClientPreviewReport(athlete)
    expect(preview.value.deal_pricing_method).toBe(CLIENT_PREVIEW_PRICING_METHOD)
    expect(preview.value.annual_nil_benchmark).toBeNull()
    expect(preview.value.total_benchmark).toBeNull()
    expect(preview.value.activation_deal_mid).toBeNull()
    expect(preview.value.activation_deal_low).toBeNull()
    expect(preview.value.activation_deal_high).toBeNull()
    expect(isClientPreviewValuation(preview)).toBe(true)
    expect(hasFinalCscValuations(preview)).toBe(false)
  })

  it('normalizeCscReport(null) stays a non-final preview', () => {
    const normalized = normalizeCscReport(null, athlete)
    expect(isClientPreviewValuation(normalized)).toBe(true)
    expect(hasFinalCscValuations(normalized)).toBe(false)
    expect(normalized.value.annual_nil_benchmark).toBeNull()
    expect(normalized.value.activation_deal_mid).toBeNull()
  })
})

describe('normalizeCscReport live merge', () => {
  it('preserves API valuations and does not overwrite with athlete-card dollars', () => {
    const normalized = normalizeCscReport(liveReport(), athlete)
    expect(isClientPreviewValuation(normalized)).toBe(false)
    expect(hasFinalCscValuations(normalized)).toBe(true)
    expect(normalized.value.annual_nil_benchmark).toBe(3_700_000)
    expect(normalized.value.activation_deal_mid).toBe(54_000)
  })

  it('leaves missing money null instead of inventing athlete-card fallbacks', () => {
    const sparse = liveReport({
      total_benchmark: null,
      annual_nil_benchmark: null,
      activation_deal_low: null,
      activation_deal_mid: null,
      activation_deal_high: null,
      range_low: null,
      range_high: null,
      deal_pricing_method: 'deal_pricing_v2',
    })
    const normalized = normalizeCscReport(sparse, athlete)
    expect(normalized.value.annual_nil_benchmark).toBeNull()
    expect(normalized.value.activation_deal_mid).toBeNull()
    expect(normalized.value.total_benchmark).toBeNull()
    // Not a client preview method, but still not displayable as final money.
    expect(isClientPreviewValuation(normalized)).toBe(false)
    expect(hasFinalCscValuations(normalized)).toBe(false)
  })
})
