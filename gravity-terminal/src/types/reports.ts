import type { AthleteRecord, ComparableRecord } from './athlete'

export interface CscReportComparablesRow extends ComparableRecord {
  deal_structure?: string | null
  verified_source?: string | null
  confidence?: number | null
}

export interface CscReportJson {
  executive_summary: string
  gravity_score_table: string
  comparables_analysis: CscReportComparablesRow[]
  nil_range_note: string
  shap_narrative: string
  risk_assessment: string
  methodology: string
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
