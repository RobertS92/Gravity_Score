import { apiGet } from './client'

export type ScraperJobRow = {
  job_type?: string
  status?: string
  processed_count?: number
  failed_count?: number
  started_at?: string
  completed_at?: string | null
  progress?: Record<string, unknown> | null
}

export type OperationsDashboard = {
  generated_at: string
  database: {
    athletes_total?: number | null
    athletes_with_scores?: number | null
    athletes_last_scraped_set?: number | null
    athletes_scraped_7d?: number | null
    avg_data_quality_score?: string | number | null
    athletes_with_dqs?: number | null
    raw_athlete_data_rows?: number | null
    raw_athlete_data_latest?: string | null
    roster_snapshots_rows?: number | null
    roster_snapshots_latest?: string | null
    scraper_jobs_in_db?: boolean
    scraper_jobs_recent?: ScraperJobRow[]
    athletes_roster_verified?: number | null
    athletes_roster_verified_180d?: number | null
  }
  scrapers: {
    health?: Record<string, unknown>
    jobs_status?: unknown
    jobs_progress?: Record<string, unknown>
  } | null
  scrapers_error?: string | null
}

export function fetchOperationsDashboard(): Promise<OperationsDashboard> {
  return apiGet<OperationsDashboard>('operations/dashboard')
}
