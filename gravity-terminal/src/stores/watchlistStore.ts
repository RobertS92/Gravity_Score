import { create } from 'zustand'
import { getAthlete } from '../api/athletes'
import { addToWatchlistApi, getWatchlist, removeFromWatchlistApi } from '../api/watchlist'
import type { AthleteRecord } from '../types/athlete'
import { getTerminalUserId } from './authStore'
import { useFeedStore } from './feedStore'

let refreshTimer: ReturnType<typeof setInterval> | null = null

export type WatchlistStore = {
  athletes: AthleteRecord[]
  isLoading: boolean
  loadWatchlist: () => Promise<void>
  addToWatchlist: (id: string) => Promise<void>
  removeFromWatchlist: (id: string) => Promise<void>
}

export const useWatchlistStore = create<WatchlistStore>((set, get) => ({
  athletes: [],
  isLoading: false,

  loadWatchlist: async () => {
    const userId = getTerminalUserId()
    if (!userId) {
      set({ athletes: [], isLoading: false })
      return
    }
    set({ isLoading: true })
    try {
      const athletes = await getWatchlist(userId)
      set({ athletes, isLoading: false })
      // Start Realtime feed for all watchlist athletes
      const ids = athletes.map((a) => a.athlete_id)
      useFeedStore.getState().startRealtimeFeed(ids)
    } catch {
      set({ isLoading: false })
    }
  },

  addToWatchlist: async (id: string) => {
    if (get().athletes.some((a) => a.athlete_id === id)) return
    // Optimistic: fetch the athlete record for immediate UI update
    let optimistic: AthleteRecord | null = null
    try {
      optimistic = await getAthlete(id)
      set({ athletes: [...get().athletes, optimistic] })
    } catch {
      /* will still try API write */
    }
    try {
      await addToWatchlistApi(id)
    } catch {
      // Rollback optimistic add on API failure
      if (optimistic) {
        set({ athletes: get().athletes.filter((a) => a.athlete_id !== id) })
      }
    }
  },

  removeFromWatchlist: async (id: string) => {
    // Optimistic remove
    const prev = get().athletes
    set({ athletes: prev.filter((a) => a.athlete_id !== id) })
    try {
      await removeFromWatchlistApi(id)
    } catch {
      // Rollback on failure
      set({ athletes: prev })
    }
  },
}))

export function startWatchlistRefresh() {
  if (refreshTimer) clearInterval(refreshTimer)
  refreshTimer = setInterval(() => {
    void useWatchlistStore.getState().loadWatchlist()
  }, 5 * 60_000)
}
