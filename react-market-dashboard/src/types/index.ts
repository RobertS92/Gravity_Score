export type DataMode = 'ecos' | 'nfl'

export interface FinancialOverview {
  total_market_value: number
  active_contracts: number
  avg_brand_value: number
  market_activity: number
  athlete_count: number
}

export interface TopPerformer {
  rank: number
  name: string
  position: string
  team: string
  brand_value: number
  change_pct: number
}

export interface MarketActivity {
  time: string
  type: string
  tag_class: string
  priority: string
  description: string
}

export interface QuickStats {
  teams_tracked: number
  data_points: string
  update_freq: string
}

export interface SystemStatus {
  api_status: string
  data_freshness: string
  sync_rate: string
}