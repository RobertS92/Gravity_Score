import type { AthleteRecord, AthleteSearchHit, ComparableRecord, ScoreHistoryPoint } from '../types/athlete'
import type { FeedEventRecord } from '../types/feed'
import {
  mapAthleteFromBundle,
  mapComparablesFromBundle,
  mapFeedEvents,
  mapScoreHistoryFromApi,
  type AthleteDetailBundle,
} from './adapters/athlete'
import { apiGet } from './client'

export type AthleteDetailResult = {
  athlete: AthleteRecord
  comparables: ComparableRecord[]
  scoreHistory: ScoreHistoryPoint[]
}

/** Single round-trip: profile + comparables + score history (production API bundle). */
export async function fetchAthleteDetail(athleteId: string): Promise<AthleteDetailResult> {
  const raw = await apiGet<AthleteDetailBundle>(`athletes/${athleteId}`)
  const athlete = mapAthleteFromBundle(raw)
  const comparables = mapComparablesFromBundle(
    raw.comparables as Record<string, unknown>[] | undefined,
    athlete.gravity_score ?? null,
  )
  const scoreHistory = mapScoreHistoryFromApi(
    (raw.score_history ?? []) as Record<string, unknown>[],
  )
  return { athlete, comparables, scoreHistory }
}

/** @deprecated Prefer fetchAthleteDetail — kept for callers expecting a flat record only. */
export async function getAthlete(id: string): Promise<AthleteRecord> {
  const { athlete } = await fetchAthleteDetail(id)
  return athlete
}

function normalizeSearchResponse(raw: unknown): AthleteSearchHit[] {
  const rows: unknown[] = Array.isArray(raw)
    ? raw
    : raw && typeof raw === 'object' && Array.isArray((raw as { athletes?: unknown }).athletes)
      ? ((raw as { athletes: unknown[] }).athletes ?? [])
      : []
  const out: AthleteSearchHit[] = []
  for (const row of rows) {
    if (!row || typeof row !== 'object') continue
    const r = row as Record<string, unknown>
    const id = r.athlete_id ?? r.id
    const name = r.name
    if (typeof id === 'string' && id && typeof name === 'string') {
      out.push({ athlete_id: id, name })
    }
  }
  return out
}

function normalizeSearchFull(raw: unknown): AthleteRecord[] {
  const rows: unknown[] = Array.isArray(raw)
    ? raw
    : raw && typeof raw === 'object' && Array.isArray((raw as { athletes?: unknown }).athletes)
      ? ((raw as { athletes: unknown[] }).athletes ?? [])
      : []
  const out: AthleteRecord[] = []
  for (const row of rows) {
    if (!row || typeof row !== 'object') continue
    const r = row as Record<string, unknown>
    const id = (r.athlete_id ?? r.id) as string | undefined
    const name = r.name as string | undefined
    if (!id || !name) continue
    out.push({
      athlete_id: id,
      name,
      position: (r.position as string) ?? null,
      school: (r.school as string) ?? null,
      conference: (r.conference as string) ?? null,
      sport: (r.sport as string) ?? null,
      gravity_score: r.gravity_score != null ? Number(r.gravity_score) : null,
      proof_score: r.proof_score != null ? Number(r.proof_score) : null,
      dollar_p50_usd: r.dollar_p50_usd != null ? Number(r.dollar_p50_usd) : null,
    })
  }
  return out
}

export function searchAthletes(query: string) {
  const q = query.trim()
  if (!q) return Promise.resolve([] as AthleteSearchHit[])
  return apiGet<unknown>(`athletes?q=${encodeURIComponent(q)}&limit=25`).then(normalizeSearchResponse)
}

/** Search with optional filter params, returns full AthleteRecord (score, school, etc.). */
export function searchAthletesFiltered(params: Record<string, string>): Promise<AthleteRecord[]> {
  const qs = new URLSearchParams({ limit: '30', ...params }).toString()
  return apiGet<unknown>(`athletes?${qs}`).then(normalizeSearchFull)
}

export async function getComparables(id: string): Promise<ComparableRecord[]> {
  const raw = await apiGet<{ comparables: Record<string, unknown>[] }>(`athletes/${id}/comparables`)
  return mapComparablesFromBundle(raw.comparables ?? [], null)
}

export async function getFeed(id: string): Promise<FeedEventRecord[]> {
  const raw = await apiGet<{ events: Record<string, unknown>[] }>(`athletes/${id}/feed`)
  return mapFeedEvents(raw.events ?? [])
}

export async function getScoreHistory(id: string): Promise<ScoreHistoryPoint[]> {
  const raw = await apiGet<{ history: Record<string, unknown>[] }>(`athletes/${id}/score-history`)
  return mapScoreHistoryFromApi(raw.history ?? [])
}
