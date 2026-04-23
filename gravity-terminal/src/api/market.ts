import type { AthleteRecord } from '../types/athlete'
import type { SchoolIndexRow } from '../types/reports'
import { mapSearchRowToAthlete } from './adapters/athlete'
import { apiGet } from './client'

export type MarketScanQuery = {
  sport?: string
  /** Comma-separated CFB,NCAAB,NCAAW (API `sports` query). */
  sports?: string
  position?: string
  conference?: string
  min_score?: number
  /** If true, show athletes with roster_verified_at older than API threshold (still excludes is_active=false). */
  include_stale_roster?: boolean
}

export type MarketScanResult = {
  athletes: AthleteRecord[]
  /** Total rows matching filters (across all pages). */
  total: number
}

const PAGE_SIZE = 500
/** Safety cap so the browser does not load unbounded rows. */
export const MARKET_SCAN_ROW_CAP = 12000
const MAX_LOADED = MARKET_SCAN_ROW_CAP

function buildMarketScanSearchParams(q: MarketScanQuery, offset: number, limit: number): string {
  const sp = new URLSearchParams()
  sp.set('limit', String(limit))
  sp.set('offset', String(offset))
  if (q.sport) sp.set('sport', q.sport)
  if (q.sports) sp.set('sports', q.sports)
  if (q.position) sp.set('position_group', q.position)
  if (q.conference) sp.set('conference', q.conference)
  if (q.min_score != null) sp.set('min_gravity', String(q.min_score))
  if (q.include_stale_roster) sp.set('include_stale_roster', 'true')
  return sp.toString()
}

/**
 * Loads market scan rows in pages until all matching athletes are fetched (up to MAX_LOADED).
 */
export async function getMarketScan(q: MarketScanQuery = {}): Promise<MarketScanResult> {
  const out: AthleteRecord[] = []
  let offset = 0
  let total = 0

  while (offset < MAX_LOADED) {
    const qs = buildMarketScanSearchParams(q, offset, PAGE_SIZE)
    const raw = await apiGet<{
      athletes: Record<string, unknown>[]
      total?: number
      returned?: number
    }>(`market/scan?${qs}`)
    const batch = (raw.athletes ?? []).map((r) => mapSearchRowToAthlete(r))
    if (offset === 0 && typeof raw.total === 'number') {
      total = raw.total
    }
    out.push(...batch)
    const n = batch.length
    if (n === 0) break
    if (n < PAGE_SIZE) break
    if (total > 0 && out.length >= total) break
    offset += n
    if (out.length >= MAX_LOADED) break
  }

  if (total === 0 && out.length > 0) {
    total = out.length
  }

  return { athletes: out, total }
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
