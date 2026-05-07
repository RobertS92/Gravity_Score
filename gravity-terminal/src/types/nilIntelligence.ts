export type DealActionRecommendation = 'OFFER_NOW' | 'NEGOTIATE' | 'WAIT' | 'PASS'
export type DecisionUrgency = 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
export type ConfidenceLevel = 'LOW' | 'MEDIUM' | 'HIGH'

export interface DealActionStructure {
  structure_type: 'fixed' | 'hybrid' | 'performance_heavy'
  term_months: number
  upfront_pct: number
  incentive_pct: number
  notes: string
}

export interface DealActionResponse {
  athlete_id: string
  recommendation: DealActionRecommendation
  urgency: DecisionUrgency
  recommended_range_low_usd: number
  recommended_range_high_usd: number
  walk_away_price_usd: number
  rationale: string[]
  structure: DealActionStructure
  generated_at: string
}

export interface ConfidenceFactor {
  key: string
  label: string
  score: number
  weight: number
  detail: string
}

export interface ConfidenceResponse {
  athlete_id: string
  overall_score: number
  overall_label: ConfidenceLevel
  factors: ConfidenceFactor[]
  caveats: string[]
  freshness: {
    score_last_updated_at: string | null
    data_last_verified_at: string | null
  }
  comparables: {
    cohort_size: number
    verified_deals_in_cohort: number
    median_similarity: number | null
  }
}

export interface AlternativeCandidate {
  athlete_id: string
  name: string
  school: string | null
  position: string | null
  gravity_score: number | null
  nil_valuation_consensus: number | null
  risk_score: number | null
  fit_score: number
  expected_savings_vs_subject_usd: number | null
  why_better: string
}

export interface AlternativesResponse {
  athlete_id: string
  generated_at: string
  alternatives: AlternativeCandidate[]
}
