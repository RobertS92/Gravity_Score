/**
 * Supabase Realtime client — used for live score updates and event feed.
 *
 * Requires env vars:
 *   VITE_SUPABASE_URL        - e.g. https://abcdef.supabase.co
 *   VITE_SUPABASE_ANON_KEY   - public anon key from Supabase dashboard
 *
 * Falls back to null (no realtime) if env vars are missing,
 * so the app continues to work via polling as before.
 */

import { createClient, type SupabaseClient, type RealtimeChannel } from '@supabase/supabase-js'

const SUPABASE_URL = (import.meta.env.VITE_SUPABASE_URL as string | undefined) ?? ''
const SUPABASE_ANON_KEY = (import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined) ?? ''

let _client: SupabaseClient | null = null

export function getSupabaseClient(): SupabaseClient | null {
  if (!SUPABASE_URL || !SUPABASE_ANON_KEY) return null
  if (!_client) {
    _client = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      realtime: { params: { eventsPerSecond: 10 } },
    })
  }
  return _client
}

export function isRealtimeAvailable(): boolean {
  return Boolean(SUPABASE_URL && SUPABASE_ANON_KEY)
}

// ------------------------------------------------------------------
// Score update subscription
// ------------------------------------------------------------------

/** Called when athlete_gravity_scores row changes for the given athlete. */
export type ScoreUpdatePayload = {
  athlete_id: string
  gravity_score: number
  brand_score: number
  proof_score: number
  proximity_score: number
  velocity_score: number
  risk_score: number
  calculated_at: string
}

let _scoreChannel: RealtimeChannel | null = null

export function subscribeToAthleteScore(
  athleteId: string,
  onUpdate: (payload: ScoreUpdatePayload) => void,
): () => void {
  const client = getSupabaseClient()
  if (!client) return () => {}

  _scoreChannel?.unsubscribe()

  _scoreChannel = client
    .channel(`score-${athleteId}`)
    .on(
      'postgres_changes',
      {
        event: 'UPDATE',
        schema: 'public',
        table: 'athlete_gravity_scores',
        filter: `athlete_id=eq.${athleteId}`,
      },
      (payload) => {
        const row = payload.new as ScoreUpdatePayload
        if (row?.athlete_id) onUpdate(row)
      },
    )
    .subscribe()

  return () => {
    _scoreChannel?.unsubscribe()
    _scoreChannel = null
  }
}

// ------------------------------------------------------------------
// Live event feed subscription
// ------------------------------------------------------------------

/** Shape of a row from athlete_events as it arrives via Realtime. */
export type AthleteEventPayload = {
  id: string
  athlete_id: string
  event_type: string
  event_source: string
  event_data: Record<string, unknown>
  signal_strength: number
  occurred_at: string
  processed_at: string | null
  score_impact: Record<string, number> | null
}

let _feedChannel: RealtimeChannel | null = null

export function subscribeToWatchlistFeed(
  watchlistAthleteIds: string[],
  onEvent: (payload: AthleteEventPayload) => void,
): () => void {
  const client = getSupabaseClient()
  if (!client || watchlistAthleteIds.length === 0) return () => {}

  _feedChannel?.unsubscribe()

  // Supabase Realtime filter supports IN for up to ~20 IDs.
  // For larger watchlists we subscribe to all events and filter client-side.
  const idSet = new Set(watchlistAthleteIds)
  const useFilter = watchlistAthleteIds.length <= 20

  const channelConfig = useFilter
    ? {
        event: 'INSERT' as const,
        schema: 'public',
        table: 'athlete_events',
        filter: `athlete_id=in.(${watchlistAthleteIds.join(',')})`,
      }
    : {
        event: 'INSERT' as const,
        schema: 'public',
        table: 'athlete_events',
      }

  _feedChannel = client
    .channel('watchlist-feed')
    .on('postgres_changes', channelConfig, (payload) => {
      const row = payload.new as AthleteEventPayload
      if (!row?.id) return
      // Client-side filter for large watchlists
      if (!useFilter && !idSet.has(row.athlete_id)) return
      // Skip low-signal housekeeping events from the feed UI
      if (['news_mention_update', 'social_follower_update'].includes(row.event_type)) return
      onEvent(row)
    })
    .subscribe()

  return () => {
    _feedChannel?.unsubscribe()
    _feedChannel = null
  }
}
