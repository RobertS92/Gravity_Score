import { apiGet } from './client'

export type VerificationLevel =
  | 'OFFICIAL'
  | 'MULTI_SOURCE'
  | 'SINGLE_SOURCE'
  | 'LOW_CONFIDENCE'
  | 'UNVERIFIED'

export type FeedItem = {
  id: string
  kind: 'athlete_event' | 'nil_deal' | 'team_event'
  category: string
  title: string | null
  body: string | null
  occurred_at: string | null
  published_at?: string | null
  // Provenance — populated post-migration 012.
  source: string | null
  source_domain?: string | null
  source_url: string | null
  source_tier?: number | null
  verification?: VerificationLevel | null
  confidence_score?: number | null
  exact_quote?: string | null
  correction_note?: string | null
  athlete_id: string | null
  athlete_name: string | null
  team_id: string | null
  team_name: string | null
  sport: string | null
  metadata: Record<string, unknown> | null
}

export type FeedResponse = {
  items: FeedItem[]
  next_before: string | null
}

export type FeedSource = 'watchlist' | 'teams' | 'general'

export type FeedQuery = {
  sources?: FeedSource[]
  categories?: string[]
  sports?: string[]
  before?: string
  limit?: number
  /** Minimum trust level. Default = SINGLE_SOURCE on the backend. */
  min_verification?: VerificationLevel
}

function buildQuery(q: FeedQuery): string {
  const sp = new URLSearchParams()
  if (q.sources && q.sources.length) sp.set('sources', q.sources.join(','))
  if (q.categories && q.categories.length) sp.set('categories', q.categories.join(','))
  if (q.sports && q.sports.length) sp.set('sports', q.sports.join(','))
  if (q.before) sp.set('before', q.before)
  if (q.limit) sp.set('limit', String(q.limit))
  if (q.min_verification) sp.set('min_verification', q.min_verification)
  const s = sp.toString()
  return s ? `?${s}` : ''
}

export async function fetchFeed(q: FeedQuery = {}): Promise<FeedResponse> {
  return apiGet<FeedResponse>(`feed${buildQuery(q)}`)
}

export type FeedCatalog = {
  categories: string[]
  default_general_categories?: string[]
  sources: string[]
  verification_levels?: VerificationLevel[]
  default_min_verification?: VerificationLevel
}

export async function fetchFeedCatalog(): Promise<FeedCatalog> {
  return apiGet<FeedCatalog>('feed/categories')
}
