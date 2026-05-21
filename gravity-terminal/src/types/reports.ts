import type { AthleteRecord, ComparableRecord } from './athlete'

export interface CscReportComparablesRow extends ComparableRecord {
  deal_structure?: string | null
  verified_source?: string | null
  confidence?: number | null
}

export type CscSignalLevel = 'High' | 'Moderate' | 'Low'

export interface CscValueSection {
  total_benchmark: number | null
  range_low: number | null
  range_high: number | null
  tier_tag?: string | null
  confidence_tag?: string | null
}

export interface CscKeyValueDriver {
  label: string
  signal: CscSignalLevel
  explanation: string
}

export interface CscExplanationSection {
  executive_summary: string
  key_value_drivers: CscKeyValueDriver[]
  driver_takeaway: string
}

export interface CscValidationSection {
  market_context: string
  comparable_tier: string
  example_comparables: CscReportComparablesRow[]
  takeaway: string
  comparable_state: 'sufficient' | 'sparse' | 'none'
  positional_reference_athletes: CscReportComparablesRow[]
}

export interface CscConfidenceRiskSection {
  confidence_level: CscSignalLevel
  confidence_note: string
  risk_level: CscSignalLevel
  risk_note: string
}

export interface CscDetailSection {
  shap_attribution: string
  methodology: string
  inputs: string
}

export interface CscReportMetadata {
  tier_version: 'tier_v1' | 'tier_v2'
  tier_v1: string
  tier_v2: string
  cohort_window_days_used: number
  season_state: string
  cohort_size: number
  cohort_fallback_step: 0 | 1 | 2 | 3
  comparable_state: 'sufficient' | 'sparse' | 'none'
  comparable_sets_computed_at?: string | null
  exposure_formula_version: string
  exposure_formula_weights: {
    proximity_weight: number
    velocity_weight: number
  }
  rollout_phase: string
  low_cohort_data: boolean
  athlete_benchmark_percentile_in_cohort?: number | null
}

export interface CscReportJson {
  value: CscValueSection
  explanation: CscExplanationSection
  validation: CscValidationSection
  confidence_risk: CscConfidenceRiskSection
  detail: CscDetailSection
  metadata: CscReportMetadata
  /** Legacy fields accepted during backend rollout; prefer sectioned fields above. */
  executive_summary?: string
  gravity_score_table?: string
  comparables_analysis?: CscReportComparablesRow[]
  nil_range_note?: string
  shap_narrative?: string
  risk_assessment?: string
  methodology?: string
}

export interface CscReportParams {
  sport?: string
  position?: string
  comparables_count?: number
  confidence_min?: number
  csc_band_low_pct?: number
  csc_band_high_pct?: number
  date_from?: string
  date_to?: string
  verified_only?: boolean
}

export interface BrandMatchBrief {
  budget: number
  category: string
  geography: string[]
  audience: string[]
  risk_tolerance: number
  max_transfer_risk: boolean
  authenticity_weight: number
  min_social_reach?: number
  prioritize_engagement?: boolean
  excluded_categories?: string[]
  deal_density_preference?: 'few' | 'moderate' | 'any'
  sports?: string[]
}

export interface BrandMatchBreakdown {
  brand_alignment: number
  geography_overlap: number
  category_authenticity: number
  engagement_quality: number
  risk_alignment: number
}

export interface BrandMatchResult {
  athlete_id: string
  name: string
  school?: string | null
  position?: string | null
  match_score: number
  gravity_score?: number | null
  brand_score?: number | null
  deal_range_low?: number | null
  deal_range_high?: number | null
  fit_rationale?: string
  social_combined_reach?: number | null
  instagram_engagement_rate?: number | null
  verified_deals_count?: number | null
  sport?: string | null
  class_year?: string | null
  conference?: string | null
  match_breakdown?: BrandMatchBreakdown
  recommended_structure?: 'FIXED' | 'PERFORMANCE_WEIGHTED' | 'HYBRID'
  exclusion_flags?: string[]
  athlete?: AthleteRecord
}

export interface SchoolIndexRow {
  team_id?: string | null
  school: string
  conference?: string | null
  sport?: string | null
  avg_gravity_score?: number | null
  program_gravity_score?: number | null
  program_brand_score?: number | null
  program_proof_score?: number | null
  program_velocity_score?: number | null
  program_risk_score?: number | null
  athlete_count?: number | null
  watchlisted_count?: number | null
  top_athlete_name?: string | null
  nil_market_size_estimate?: number | null
}
