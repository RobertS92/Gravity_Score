import type { AthleteRecord } from '../types/athlete'
import type { SchoolIndexRow } from '../types/reports'
import { mapSearchRowToAthlete } from './adapters/athlete'
import { apiGet } from './client'

export type MarketScanQuery = {
  sport?: string
  position?: string
  conference?: string
  min_score?: number
}

export async function getMarketScan(q: MarketScanQuery): Promise<AthleteRecord[]> {
  const sp = new URLSearchParams()
  if (q.sport) sp.set('sport', q.sport)
  if (q.position) sp.set('position_group', q.position)
  if (q.conference) sp.set('conference', q.conference)
  if (q.min_score != null) sp.set('min_gravity', String(q.min_score))
  const qs = sp.toString()
  const raw = await apiGet<{ athletes: Record<string, unknown>[] }>(
    `market/scan${qs ? `?${qs}` : ''}`,
  )
  return (raw.athletes ?? []).map((r) => mapSearchRowToAthlete(r))
}

export async function getMarketSchools(): Promise<SchoolIndexRow[]> {
  const raw = await apiGet<{ schools: Record<string, unknown>[] }>('market/schools')
  return (raw.schools ?? []).map((row) => ({
    school: String(row.school ?? ''),
    conference: row.conference != null ? String(row.conference) : null,
    avg_gravity_score: row.avg_gravity_score != null ? Number(row.avg_gravity_score) : null,
    watchlisted_count: row.watchlisted_count != null ? Number(row.watchlisted_count) : null,
    top_athlete_name: row.top_athlete_name != null ? String(row.top_athlete_name) : null,
    nil_market_size_estimate:
      row.nil_market_size_estimate != null ? Number(row.nil_market_size_estimate) : null,
  }))
}
