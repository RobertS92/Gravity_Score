import { create } from 'zustand'
import { fetchAthleteDetail } from '../api/athletes'
import type { AthleteRecord, ComparableRecord, ScoreHistoryPoint } from '../types/athlete'
import {
  subscribeToAthleteScore,
  type ScoreUpdatePayload,
} from '../lib/supabaseRealtime'

const BUNDLE_PREFIX = 'gravity_bundle_v2_'

let _unsubscribeScore: (() => void) | null = null

interface Bundle {
  athlete: AthleteRecord
  comparables: ComparableRecord[]
  scoreHistory: ScoreHistoryPoint[]
}

function readBundle(id: string): Bundle | null {
  try {
    const raw = localStorage.getItem(BUNDLE_PREFIX + id)
    if (!raw) return null
    return JSON.parse(raw) as Bundle
  } catch {
    return null
  }
}

function writeBundle(id: string, b: Bundle) {
  try {
    localStorage.setItem(BUNDLE_PREFIX + id, JSON.stringify(b))
  } catch {
    /* ignore quota */
  }
}

export type AthleteStore = {
  activeAthleteId: string | null
  activeAthlete: AthleteRecord | null
  comparables: ComparableRecord[]
  scoreHistory: ScoreHistoryPoint[]
  isLoading: boolean
  error: string | null
  scoreAnimationPending: boolean
  liveScoreActive: boolean
  setActiveAthlete: (id: string) => Promise<void>
  refreshActiveAthlete: () => Promise<void>
  clearActiveAthlete: () => void
  consumeScoreAnimation: () => void
  applyLiveScore: (payload: ScoreUpdatePayload) => void
}

export const useAthleteStore = create<AthleteStore>((set, get) => ({
  activeAthleteId: null,
  activeAthlete: null,
  comparables: [],
  scoreHistory: [],
  isLoading: false,
  error: null,
  scoreAnimationPending: false,
  liveScoreActive: false,

  consumeScoreAnimation: () => set({ scoreAnimationPending: false }),

  /** Apply a live score update from Supabase Realtime without a full API refetch. */
  applyLiveScore: (payload: ScoreUpdatePayload) => {
    const { activeAthlete } = get()
    if (!activeAthlete) return
    const updated: AthleteRecord = {
      ...activeAthlete,
      gravity_score:    payload.gravity_score    ?? activeAthlete.gravity_score,
      brand_score:      payload.brand_score       ?? activeAthlete.brand_score,
      proof_score:      payload.proof_score       ?? activeAthlete.proof_score,
      proximity_score:  payload.proximity_score   ?? activeAthlete.proximity_score,
      velocity_score:   payload.velocity_score    ?? activeAthlete.velocity_score,
      risk_score:       payload.risk_score        ?? activeAthlete.risk_score,
    }
    writeBundle(activeAthlete.athlete_id, {
      athlete: updated,
      comparables: get().comparables,
      scoreHistory: get().scoreHistory,
    })
    set({ activeAthlete: updated, scoreAnimationPending: true })
    window.setTimeout(() => get().consumeScoreAnimation(), 1200)
  },

  clearActiveAthlete: () => {
    if (_unsubscribeScore) {
      _unsubscribeScore()
      _unsubscribeScore = null
    }
    set({
      activeAthleteId: null,
      activeAthlete: null,
      comparables: [],
      scoreHistory: [],
      error: null,
      scoreAnimationPending: false,
      liveScoreActive: false,
    })
  },

  setActiveAthlete: async (id: string) => {
    const prevId = get().activeAthleteId
    const bundle = readBundle(id)

    // Cancel previous live score subscription
    if (_unsubscribeScore) {
      _unsubscribeScore()
      _unsubscribeScore = null
    }

    if (bundle) {
      set({
        activeAthleteId: id,
        activeAthlete: bundle.athlete,
        comparables: bundle.comparables,
        scoreHistory: bundle.scoreHistory,
        isLoading: false,
        error: null,
        scoreAnimationPending: prevId !== id,
        liveScoreActive: false,
      })
    } else {
      set({
        activeAthleteId: id,
        isLoading: true,
        error: null,
        scoreAnimationPending: prevId !== id,
        liveScoreActive: false,
      })
    }

    try {
      const { athlete, comparables, scoreHistory } = await fetchAthleteDetail(id)
      writeBundle(id, { athlete, comparables, scoreHistory })
      try {
        localStorage.setItem('gravity_last_athlete_id', id)
      } catch {
        /* ignore */
      }
      set({
        activeAthleteId: id,
        activeAthlete: athlete,
        comparables,
        scoreHistory,
        isLoading: false,
        error: null,
      })
    } catch (e) {
      if (!bundle) {
        set({
          isLoading: false,
          error: e instanceof Error ? e.message : 'Failed to load athlete',
        })
      }
    }

    // Subscribe to live score updates for this athlete via Supabase Realtime
    _unsubscribeScore = subscribeToAthleteScore(id, (payload) => {
      get().applyLiveScore(payload)
    })
    if (_unsubscribeScore !== null) {
      set({ liveScoreActive: true })
    }
  },

  refreshActiveAthlete: async () => {
    const id = get().activeAthleteId
    if (!id) return
    set({ scoreAnimationPending: false })
    try {
      const { athlete, comparables, scoreHistory } = await fetchAthleteDetail(id)
      writeBundle(id, { athlete, comparables, scoreHistory })
      set({ activeAthlete: athlete, comparables, scoreHistory, error: null })
    } catch {
      /* keep stale */
    }
  },
}))
