import type { AthleteRecord } from '../types/athlete'
import type { SchoolIndexRow } from '../types/reports'
import { parseFiniteNumber } from '../lib/numberParsing'
import { mapSearchRowToAthlete } from './adapters/athlete'
import { apiGet } from './client'

export type MarketScanQuery = {
  sport?: string
  /** Comma-separated CFB,NCAAB,NCAAW (API `sports` query). */
  sports?: string
  position?: string
  conference?: string
  min_score?: number
  include_stale_roster?: boolean
  /** Cap rows loaded client-side. Agent tools should pass a small value. */
  maxLoaded?: number
}

export type MarketScanRosterWindow = 'live' | 'stale' | 'stale_fallback'

export type MarketScanResult = {
  athletes: AthleteRecord[]
  /** Total rows matching filters (across all pages). */
  total: number
  rosterWindow: MarketScanRosterWindow | null
}

const PAGE_SIZE = 500
/** Safety cap so the browser does not load unbounded rows. */
export const MARKET_SCAN_ROW_CAP = 12000
const MAX_LOADED = MARKET_SCAN_ROW_CAP

function buildMarketScanSearchParams(
  q: MarketScanQuery,
  offset: number,
  limit: number,
  includeStaleRoster: boolean,
): string {
  const sp = new URLSearchParams()
  sp.set('limit', String(limit))
  sp.set('offset', String(offset))
  if (q.sport) sp.set('sport', q.sport)
  if (q.sports) sp.set('sports', q.sports)
  if (q.position) sp.set('position_group', q.position)
  if (q.conference) sp.set('conference', q.conference)
  if (q.min_score != null) sp.set('min_gravity', String(q.min_score))
  if (includeStaleRoster) sp.set('include_stale_roster', 'true')
  return sp.toString()
}

function parseRosterWindow(raw: unknown): MarketScanRosterWindow | null {
  if (raw === 'live' || raw === 'stale' || raw === 'stale_fallback') return raw
  return null
}

type ScanPage = {
  athletes: AthleteRecord[]
  total: number
  rosterWindow: MarketScanRosterWindow | null
}

async function fetchMarketScanPage(
  q: MarketScanQuery,
  offset: number,
  includeStaleRoster: boolean,
  limit: number,
  signal?: AbortSignal,
): Promise<ScanPage> {
  const qs = buildMarketScanSearchParams(q, offset, limit, includeStaleRoster)
  const raw = await apiGet<{
    athletes: Record<string, unknown>[]
    total?: number
    returned?: number
    roster_window?: string
  }>(`market/scan?${qs}`, { signal })
  return {
    athletes: (raw.athletes ?? []).map((r) => mapSearchRowToAthlete(r)),
    total: typeof raw.total === 'number' ? raw.total : 0,
    rosterWindow: parseRosterWindow(raw.roster_window),
  }
}

/**
 * Loads market scan rows in pages until all matching athletes are fetched (up to MAX_LOADED).
 * When the live roster window is empty, retries with include_stale_roster so the table
 * still shows current-roster athletes (same fallback as terminal bootstrap).
 */
export async function getMarketScan(
  q: MarketScanQuery = {},
  opts?: { onPage?: (partial: MarketScanResult) => void; signal?: AbortSignal },
): Promise<MarketScanResult> {
  const out: AthleteRecord[] = []
  const maxLoaded = Math.min(Math.max(1, q.maxLoaded ?? MAX_LOADED), MAX_LOADED)
  let offset = 0
  let includeStale = Boolean(q.include_stale_roster)
  let total = 0
  let rosterWindow: MarketScanRosterWindow | null = includeStale ? 'stale' : null

  while (offset < maxLoaded) {
    const pageLimit = Math.min(PAGE_SIZE, maxLoaded - offset)
    if (pageLimit <= 0) break
    const batch = await fetchMarketScanPage(q, offset, includeStale, pageLimit, opts?.signal)
    if (offset === 0) {
      total = batch.total
      rosterWindow = batch.rosterWindow ?? rosterWindow
      if (!includeStale && (total === 0 || batch.rosterWindow === 'stale_fallback')) {
        includeStale = true
        rosterWindow = batch.rosterWindow === 'stale_fallback' ? 'stale_fallback' : 'stale'
        if (total === 0) {
          continue
        }
      }
    }
    out.push(...batch.athletes)
    if (total === 0 && out.length > 0) total = out.length
    if (offset === 0) {
      opts?.onPage?.({ athletes: [...out], total, rosterWindow })
    }
    const n = batch.athletes.length
    if (n === 0) break
    if (n < pageLimit) break
    if (total > 0 && out.length >= total) break
    offset += n
    if (out.length >= maxLoaded) break
  }

  return { athletes: out, total: total || out.length, rosterWindow }
}

export async function getMarketSchools(): Promise<SchoolIndexRow[]> {
  const raw = await apiGet<{ schools: Record<string, unknown>[] }>('market/schools')
  return (raw.schools ?? []).map((row) => ({
    team_id: row.team_id != null ? String(row.team_id) : null,
    school: String(row.school ?? ''),
    conference: row.conference != null ? String(row.conference) : null,
    sport: row.sport != null ? String(row.sport) : null,
    avg_gravity_score: parseFiniteNumber(row.avg_gravity_score),
    program_gravity_score:
      parseFiniteNumber(row.program_gravity_score) ?? parseFiniteNumber(row.avg_gravity_score),
    program_brand_score: parseFiniteNumber(row.program_brand_score),
    program_proof_score: parseFiniteNumber(row.program_proof_score),
    program_velocity_score: parseFiniteNumber(row.program_velocity_score),
    program_risk_score: parseFiniteNumber(row.program_risk_score),
    athlete_count: parseFiniteNumber(row.athlete_count),
    watchlisted_count: parseFiniteNumber(row.watchlisted_count),
    top_athlete_name: row.top_athlete_name != null ? String(row.top_athlete_name) : null,
    nil_market_size_estimate: parseFiniteNumber(row.nil_market_size_estimate),
  }))
}
