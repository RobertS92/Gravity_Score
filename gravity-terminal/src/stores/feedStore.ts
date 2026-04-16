import { create } from 'zustand'
import { getFeed } from '../api/athletes'
import type { FeedEventRecord } from '../types/feed'
import {
  subscribeToWatchlistFeed,
  type AthleteEventPayload,
  isRealtimeAvailable,
} from '../lib/supabaseRealtime'

let pollTimer: ReturnType<typeof setInterval> | null = null
let pollAthleteId: string | null = null
let unsubscribeFeed: (() => void) | null = null

// Human-readable labels for event types coming from athlete_events
const EVENT_TYPE_LABELS: Record<string, string> = {
  injury_report:             'Injury reported',
  injury_cleared:            'Injury cleared',
  transfer_portal_entered:   'Entered transfer portal',
  transfer_portal_committed: 'Committed to new school',
  transfer_portal_withdrawn: 'Withdrew from portal',
  nil_deal_announced:        'NIL deal announced',
  nil_valuation_updated:     'NIL valuation updated',
  social_spike:              'Social media spike',
  news_mention_surge:        'News surge',
  game_stats_updated:        'Game stats updated',
  award_announced:           'Award announced',
  recruiting_rank_changed:   'Recruiting rank changed',
  full_scrape_completed:     'Full data refresh',
}

function realtimeEventToFeedRecord(evt: AthleteEventPayload): FeedEventRecord {
  const label = EVENT_TYPE_LABELS[evt.event_type] ?? evt.event_type.replace(/_/g, ' ')
  const impact = evt.score_impact
  const delta = impact?.gravity_score
  const valueStr = delta != null ? ` (Δ${delta > 0 ? '+' : ''}${delta.toFixed(1)})` : ''

  return {
    event_id:    evt.id,
    athlete_id:  evt.athlete_id,
    event_type:  mapEventType(evt.event_type),
    timestamp:   evt.occurred_at,
    body:        `${label}${valueStr}`,
    value:       delta ?? null,
  }
}

function mapEventType(t: string): FeedEventRecord['event_type'] {
  if (t.includes('nil') || t.includes('deal')) return 'NIL_DEAL'
  if (t.includes('social') || t.includes('brand')) return 'BRAND'
  if (t.includes('news') || t.includes('velocity')) return 'VELOCITY'
  if (t.includes('injury') || t.includes('risk') || t.includes('portal')) return 'RISK'
  return 'SCORE_UPDATE'
}

function sortFeed(events: FeedEventRecord[]) {
  return [...events].sort((a, b) => (a.timestamp < b.timestamp ? 1 : -1))
}

export type FeedStore = {
  events: FeedEventRecord[]
  isLoading: boolean
  newEventIds: Set<string>
  realtimeActive: boolean
  loadFeed: (athleteId: string) => Promise<void>
  pollFeed: (athleteId: string) => void
  stopPoll: () => void
  clearNewMarks: () => void
  /** Subscribe to live events for the given watchlist athlete IDs via Supabase Realtime. */
  startRealtimeFeed: (athleteIds: string[]) => void
  stopRealtimeFeed: () => void
  addEvent: (evt: AthleteEventPayload) => void
}

export const useFeedStore = create<FeedStore>((set, get) => ({
  events: [],
  isLoading: false,
  newEventIds: new Set(),
  realtimeActive: false,

  clearNewMarks: () => set({ newEventIds: new Set() }),

  addEvent: (evt: AthleteEventPayload) => {
    const record = realtimeEventToFeedRecord(evt)
    const newIds = new Set([record.event_id])
    const events = sortFeed([record, ...get().events].slice(0, 200))
    set({ events, newEventIds: newIds })
    window.setTimeout(() => get().clearNewMarks(), 800)
  },

  loadFeed: async (athleteId: string) => {
    set({ isLoading: true })
    try {
      const prevTop = get().events[0]?.event_id
      const events = sortFeed(await getFeed(athleteId))
      const newIds = new Set<string>()
      if (prevTop && events.length && events[0].event_id !== prevTop) {
        for (const e of events) {
          if (e.event_id === prevTop) break
          newIds.add(e.event_id)
        }
      }
      set({ events, isLoading: false, newEventIds: newIds })
      if (newIds.size) {
        window.setTimeout(() => get().clearNewMarks(), 400)
      }
    } catch {
      set({ isLoading: false })
    }
  },

  startRealtimeFeed: (athleteIds: string[]) => {
    if (unsubscribeFeed) {
      unsubscribeFeed()
      unsubscribeFeed = null
    }
    if (!isRealtimeAvailable() || athleteIds.length === 0) return
    unsubscribeFeed = subscribeToWatchlistFeed(athleteIds, (evt) => {
      get().addEvent(evt)
    })
    set({ realtimeActive: true })
  },

  stopRealtimeFeed: () => {
    if (unsubscribeFeed) {
      unsubscribeFeed()
      unsubscribeFeed = null
    }
    set({ realtimeActive: false })
  },

  pollFeed: (athleteId: string) => {
    // Fall back to polling when Realtime is not configured
    if (isRealtimeAvailable()) return
    pollAthleteId = athleteId
    if (pollTimer) clearInterval(pollTimer)
    pollTimer = setInterval(() => {
      const id = pollAthleteId
      if (id) void get().loadFeed(id)
    }, 60_000)
  },

  stopPoll: () => {
    pollAthleteId = null
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  },
}))
