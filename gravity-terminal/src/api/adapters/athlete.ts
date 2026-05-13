/**
 * Map gravity_api JSON (snake_case, nested bundles) → terminal types.
 */

import type { AlertRecord, AlertSeverity, AlertType } from '../../types/alerts'
import type {
  AthleteRecord,
  ComparableRecord,
  GravityTier,
  ScoreHistoryPoint,
  ShapDrivers,
  Sport,
} from '../../types/athlete'
import type { FeedEventRecord, FeedEventType } from '../../types/feed'

const VALID_FEED_TYPES = new Set<FeedEventType>([
  'NIL_DEAL',
  'BRAND',
  'VELOCITY',
  'SCORE_UPDATE',
  'RISK',
  'TRANSFER',
  'INJURY',
  'NEWS',
  'AWARD',
  'RECRUITING',
  'PERFORMANCE',
  'ANNOUNCEMENT',
  'BUSINESS',
  'INCIDENT',
  'SCORE',
  'ROSTER',
  'SOCIAL',
  'RANKING',
  'OTHER',
])

function num(v: unknown): number | null {
  if (v == null) return null
  const n = typeof v === 'number' ? v : Number(v)
  return Number.isFinite(n) ? n : null
}

function str(v: unknown): string | null {
  if (v == null) return null
  const s = String(v)
  return s.length ? s : null
}

function tierFromScore(g: number | null): GravityTier | null {
  if (g == null) return null
  if (g >= 85) return 'ELITE'
  if (g >= 72) return 'BREAKOUT'
  if (g >= 58) return 'ESTABLISHING'
  return 'DEVELOPING'
}

export function mapSport(raw: unknown): Sport | string | null {
  const s = str(raw)?.toLowerCase()
  if (!s) return null
  if (s === 'cfb') return 'CFB'
  if (s === 'mcbb' || s === 'ncaab_mens') return 'NCAAB'
  if (s === 'wcbb' || s === 'ncaab_womens') return 'NCAAWB'
  return raw as string
}

function heightWeightFromDb(row: Record<string, unknown>) {
  const hi = num(row.height_inches)
  const wt = num(row.weight_lbs)
  const height =
    hi != null
      ? `${Math.floor(hi / 12)}'${Math.round(hi % 12)}"`
      : str(row.height)
  const weight = wt != null ? `${Math.round(wt)}lb` : str(row.weight)
  return { height, weight }
}

function shapFromScoreRow(score: Record<string, unknown> | undefined): ShapDrivers | null {
  if (!score) return null
  const raw = score.shap_values
  if (!raw || typeof raw !== 'object') return null
  const o = raw as Record<string, unknown>
  const pick = (k: string) => str(o[k])
  const out: ShapDrivers = {
    brand: pick('brand'),
    proof: pick('proof'),
    proximity: pick('proximity'),
    velocity: pick('velocity'),
    risk: pick('risk'),
  }
  if (Object.values(out).every((v) => v == null)) return null
  return out
}

function gravityDeltaWindow(history: Record<string, unknown>[]): number | null {
  if (!history.length) return null
  const latest = history[0]
  const latestScore = num(latest.gravity_score)
  const latestTsRaw = str(latest.calculated_at) ?? str(latest.date)
  if (latestScore == null || !latestTsRaw) return null
  const latestTs = Date.parse(latestTsRaw)
  if (!Number.isFinite(latestTs)) return null
  const target = latestTs - 30 * 24 * 60 * 60 * 1000
  let best: { score: number; diff: number } | null = null
  for (let i = 1; i < history.length; i++) {
    const row = history[i]
    const g = num(row.gravity_score)
    const tsRaw = str(row.calculated_at) ?? str(row.date)
    if (g == null || !tsRaw) continue
    const ts = Date.parse(tsRaw)
    if (!Number.isFinite(ts)) continue
    const diff = Math.abs(ts - target)
    if (!best || diff < best.diff) {
      best = { score: g, diff }
    }
  }
  if (!best) return null
  return Math.round((latestScore - best.score) * 10) / 10
}

function nilFromDeals(deals: unknown[]): {
  consensus: number | null
  low: number | null
  high: number | null
  verified: number
} {
  const vals: number[] = []
  let verified = 0
  for (const d of deals) {
    if (!d || typeof d !== 'object') continue
    const row = d as Record<string, unknown>
    const v = num(row.deal_value)
    if (v != null && v > 0) vals.push(v)
    if (row.verified === true) verified += 1
  }
  if (!vals.length) return { consensus: null, low: null, high: null, verified }
  const sorted = [...vals].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  const median = sorted.length % 2 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2
  return {
    consensus: median,
    low: sorted[0],
    high: sorted[sorted.length - 1],
    verified,
  }
}

function midpoint(low: number | null, high: number | null): number | null {
  if (low == null || high == null) return null
  return (low + high) / 2
}

function resolveNilConsensusFromRow(row: Record<string, unknown>): number | null {
  const p10 = num(row.dollar_p10_usd)
  const p50 = num(row.dollar_p50_usd)
  const p90 = num(row.dollar_p90_usd)
  const mid = midpoint(p10, p90)
  return num(row.nil_valuation_consensus) ?? num(row.nil_estimate) ?? p50 ?? mid ?? num(row.nil_valuation_raw)
}

function resolveComparableNilConsensusFromRow(row: Record<string, unknown>): number | null {
  const p10 = num(row.dollar_p10_usd)
  const p50 = num(row.dollar_p50_usd)
  const p90 = num(row.dollar_p90_usd)
  const mid = midpoint(p10, p90)
  return (
    num(row.deal_value)
    ?? num(row.nil_valuation_consensus)
    ?? num(row.nil_estimate)
    ?? p50
    ?? mid
    ?? num(row.nil_valuation_raw)
    ?? num(row.nil_value_raw)
    ?? num(row.nil_value_usd)
  )
}

export type AthleteDetailBundle = {
  athlete: Record<string, unknown>
  score_history: Record<string, unknown>[]
  nil_deals?: Record<string, unknown>[]
  comparables?: Record<string, unknown>[]
}

export function mapAthleteFromBundle(b: AthleteDetailBundle): AthleteRecord {
  const a = b.athlete
  const scores = b.score_history ?? []
  const latest = scores[0] as Record<string, unknown> | undefined

  const g = num(latest?.gravity_score)
  const nilAgg = nilFromDeals(b.nil_deals ?? [])
  const p10 = num(latest?.dollar_p10_usd)
  const p50 = num(latest?.dollar_p50_usd)
  const p90 = num(latest?.dollar_p90_usd)

  const { height, weight } = heightWeightFromDb(a)

  const id = str(a.id)
  if (!id) throw new Error('athlete.id missing')

  return {
    athlete_id: id,
    name: str(a.name) ?? 'Unknown',
    position: str(a.position),
    school: str(a.school),
    team_id: str(a.team_id),
    conference: str(a.conference),
    sport: mapSport(a.sport),
    class_year: str(a.eligibility_year != null ? String(a.eligibility_year) : null),
    jersey_number: str(a.jersey_number),
    height,
    weight,
    gravity_score: g,
    company_gravity_score: num(latest?.company_gravity_score),
    brand_gravity_score: num(latest?.brand_gravity_score),
    gravity_tier: tierFromScore(g),
    gravity_percentile: num(a.gravity_percentile),
    gravity_delta_30d: gravityDeltaWindow(scores),
    brand_score: num(latest?.brand_score),
    proof_score: num(latest?.proof_score),
    proximity_score: num(latest?.proximity_score),
    velocity_score: num(latest?.velocity_score),
    risk_score: num(latest?.risk_score),
    nil_valuation_consensus: nilAgg.consensus ?? p50 ?? midpoint(p10, p90) ?? num(a.nil_valuation_raw),
    nil_range_low: nilAgg.low ?? p10,
    nil_range_high: nilAgg.high ?? p90,
    nil_valuation_percentile: num(a.nil_valuation_percentile),
    nil_valuation_delta_30d: null,
    dollar_p10_usd: p10,
    dollar_p50_usd: p50,
    dollar_p90_usd: p90,
    dollar_confidence:
      latest?.dollar_confidence != null &&
      typeof latest.dollar_confidence === 'object' &&
      !Array.isArray(latest.dollar_confidence)
        ? (latest.dollar_confidence as NonNullable<AthleteRecord['dollar_confidence']>)
        : null,
    social_combined_reach: num(a.social_combined_reach),
    instagram_followers: num(a.instagram_followers),
    twitter_followers: num(a.twitter_followers),
    tiktok_followers: num(a.tiktok_followers),
    instagram_engagement_rate: num(a.instagram_engagement_rate),
    news_mentions_30d: num(a.news_mentions_30d),
    google_trends_score: num(a.google_trends_score),
    wikipedia_page_views_30d: num(a.wikipedia_page_views_30d),
    on3_nil_rank: a.on3_nil_rank != null ? String(a.on3_nil_rank) : null,
    nil_valuation_raw: num(a.nil_valuation_raw),
    data_quality_score: num(a.data_quality_score),
    verified_deals_count: nilAgg.verified,
    shap_drivers: shapFromScoreRow(latest),
    updated_at: str(latest?.calculated_at) ?? str(a.updated_at),
  }
}

export function mapScoreHistoryFromApi(history: Record<string, unknown>[]): ScoreHistoryPoint[] {
  const out: ScoreHistoryPoint[] = []
  for (const row of history) {
    const d = str(row.calculated_at) ?? str(row.date)
    const g = num(row.gravity_score)
    if (d && g != null) out.push({ date: d, gravity_score: g })
  }
  return out.reverse()
}

export function mapComparableRow(
  row: Record<string, unknown>,
  subjectGravity?: number | null,
): ComparableRecord {
  const id = str(row.id) ?? str(row.comparable_athlete_id)
  const g = num(row.gravity_score)
  const verifiedDeals =
    num(row.verified_deal_count)
    ?? num(row.verified_deals_count)
    ?? num(row.deals_verified_count)
  return {
    athlete_id: id ?? '',
    name: str(row.name) ?? '',
    school: str(row.school),
    position: str(row.position),
    gravity_score: g,
    brand_score: num(row.brand_score),
    nil_valuation_consensus: resolveComparableNilConsensusFromRow(row),
    nil_delta_vs_subject:
      subjectGravity != null && g != null ? Math.round((g - subjectGravity) * 10) / 10 : null,
    confidence: num(row.similarity_score),
    verified_deal_count: verifiedDeals,
  }
}

export function mapComparablesFromBundle(
  rows: Record<string, unknown>[] | undefined,
  subjectGravity: number | null,
): ComparableRecord[] {
  if (!rows?.length) return []
  return rows.map((r) => mapComparableRow(r, subjectGravity))
}

export function mapWatchlistAthleteRow(row: Record<string, unknown>): AthleteRecord {
  const aid = str(row.athlete_id)
  const id = str(row.id)
  const p10 = num(row.dollar_p10_usd)
  const p50 = num(row.dollar_p50_usd)
  const p90 = num(row.dollar_p90_usd)
  return {
    athlete_id: aid ?? id ?? '',
    name: str(row.name) ?? '',
    school: str(row.school),
    sport: mapSport(row.sport),
    gravity_score: num(row.gravity_score),
    company_gravity_score: num(row.company_gravity_score),
    brand_gravity_score: num(row.brand_gravity_score),
    brand_score: num(row.brand_score),
    proof_score: num(row.proof_score),
    proximity_score: num(row.proximity_score),
    velocity_score: num(row.velocity_score),
    risk_score: num(row.risk_score),
    nil_valuation_consensus: resolveNilConsensusFromRow(row),
    nil_range_low: num(row.nil_range_low) ?? p10,
    nil_range_high: num(row.nil_range_high) ?? p90,
    dollar_p10_usd: p10,
    dollar_p50_usd: p50,
    dollar_p90_usd: p90,
  }
}

export function mapAlertRow(row: Record<string, unknown>, athleteName: string): AlertRecord {
  const id = str(row.id)
  const delta = num(row.delta)
  return {
    alert_id: id ?? `alert-${String(row.created_at ?? Date.now())}`,
    athlete_id: str(row.athlete_id) ?? '',
    athlete_name: athleteName,
    school: null,
    alert_type: 'SCORE_MOVE' as AlertType,
    severity: (delta != null && Math.abs(delta) >= 5 ? 'WARN' : 'INFO') as AlertSeverity,
    description: str(row.trigger_reason) ?? 'Score change',
    numeric_change: delta,
    timestamp: str(row.created_at) ?? new Date().toISOString(),
  }
}

export function mapSearchRowToAthlete(row: Record<string, unknown>): AthleteRecord {
  const id = str(row.id) ?? str(row.athlete_id)
  const p10 = num(row.dollar_p10_usd)
  const p50 = num(row.dollar_p50_usd)
  const p90 = num(row.dollar_p90_usd)
  return {
    athlete_id: id ?? '',
    name: str(row.name) ?? '',
    school: str(row.school),
    conference: str(row.conference),
    position: str(row.position),
    sport: mapSport(row.sport),
    gravity_score: num(row.gravity_score),
    company_gravity_score: num(row.company_gravity_score),
    brand_gravity_score: num(row.brand_gravity_score),
    brand_score: num(row.brand_score),
    proof_score: num(row.proof_score),
    proximity_score: num(row.proximity_score),
    velocity_score: num(row.velocity_score),
    risk_score: num(row.risk_score),
    nil_valuation_consensus: resolveNilConsensusFromRow(row),
    nil_range_low: num(row.nil_range_low) ?? p10,
    nil_range_high: num(row.nil_range_high) ?? p90,
    dollar_p10_usd: p10,
    dollar_p50_usd: p50,
    dollar_p90_usd: p90,
    updated_at: str(row.score_date),
  }
}

export function mapFeedEvents(rows: Record<string, unknown>[]): FeedEventRecord[] {
  const out: FeedEventRecord[] = []
  for (const row of rows) {
    const rawType = str(row.event_type)
    const t = rawType ? rawType.toUpperCase() : null
    if (!t) continue
    const eventType = (VALID_FEED_TYPES.has(t as FeedEventType) ? t : 'OTHER') as FeedEventType
    out.push({
      event_id: str(row.event_id) ?? `feed-${String(row.timestamp)}-${out.length}`,
      athlete_id: str(row.athlete_id) ?? '',
      athlete_name: str(row.athlete_name),
      event_type: eventType,
      timestamp: str(row.timestamp) ?? '',
      body: str(row.body) ?? '',
      entity_name: str(row.entity_name),
      value: num(row.value),
    })
  }
  return out
}
