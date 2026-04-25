export type Sport = 'CFB' | 'NCAAB' | 'NCAAWB'
export type ClassYear = 'FR' | 'SO' | 'JR' | 'SR' | 'GS'
export type GravityTier = 'ELITE' | 'BREAKOUT' | 'ESTABLISHING' | 'DEVELOPING'

export interface ComponentDeltas {
  brand?: number | null
  proof?: number | null
  proximity?: number | null
  velocity?: number | null
  risk?: number | null
}

export interface ShapDrivers {
  brand?: string | null
  proof?: string | null
  proximity?: string | null
  velocity?: string | null
  risk?: string | null
}

export interface AthleteRecord {
  athlete_id: string
  name: string
  position?: string | null
  school?: string | null
  /** Resolved team UUID for this athlete's program (school + sport). */
  team_id?: string | null
  conference?: string | null
  sport?: Sport | string | null
  class_year?: ClassYear | string | null
  jersey_number?: string | null
  height?: string | null
  weight?: string | null
  gravity_score?: number | null
  /** Program / school Gravity (TeamGravityNet) at latest score */
  company_gravity_score?: number | null
  /** Brand-market composite (brand + velocity + proof emphasis) */
  brand_gravity_score?: number | null
  gravity_tier?: GravityTier | string | null
  gravity_percentile?: number | null
  gravity_delta_30d?: number | null
  brand_score?: number | null
  proof_score?: number | null
  proximity_score?: number | null
  velocity_score?: number | null
  risk_score?: number | null
  component_deltas?: ComponentDeltas | null
  nil_valuation_consensus?: number | null
  nil_range_low?: number | null
  nil_range_high?: number | null
  nil_valuation_percentile?: number | null
  nil_valuation_delta_30d?: number | null
  /** Model dollar quantiles (gravity_athlete_v2) */
  dollar_p10_usd?: number | null
  dollar_p50_usd?: number | null
  dollar_p90_usd?: number | null
  dollar_confidence?: {
    dollar_confidence_score?: number
    dollar_confidence_label?: string
    dollar_comparable_verified_bucket?: number
    dollar_comparable_verified_sport_position?: number
  } | null
  social_combined_reach?: number | null
  instagram_followers?: number | null
  twitter_followers?: number | null
  tiktok_followers?: number | null
  instagram_engagement_rate?: number | null
  news_mentions_30d?: number | null
  google_trends_score?: number | null
  wikipedia_page_views_30d?: number | null
  on3_nil_rank?: string | null
  verified_deals_count?: number | null
  nil_valuation_raw?: number | null
  google_trends_score_raw?: number | null
  data_quality_score?: number | null
  shap_drivers?: ShapDrivers | null
  updated_at?: string | null
}

export interface ComparableRecord {
  athlete_id: string
  name: string
  school?: string | null
  position?: string | null
  gravity_score?: number | null
  brand_score?: number | null
  nil_valuation_consensus?: number | null
  nil_delta_vs_subject?: number | null
  confidence?: number | null
  verified_deal_count?: number | null
}

export interface ScoreHistoryPoint {
  date: string
  gravity_score: number
}

/** Minimal row from GET /athletes/search */
export interface AthleteSearchHit {
  athlete_id: string
  name: string
}
