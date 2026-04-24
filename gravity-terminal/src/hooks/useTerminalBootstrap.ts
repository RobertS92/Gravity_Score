import { useEffect } from 'react'
import { searchAthletesFiltered } from '../api/athletes'
import { useAthleteStore } from '../stores/athleteStore'
import { useAuthStore } from '../stores/authStore'
import { useFeedStore } from '../stores/feedStore'
import { usePreferencesStore } from '../stores/preferencesStore'
import { useWatchlistStore, startWatchlistRefresh } from '../stores/watchlistStore'
import { useAlertStore, startAlertPolling } from '../stores/alertStore'

const LAST_KEY = 'gravity_last_athlete_id'

function readLastAthleteId(): string | null {
  try {
    const v = localStorage.getItem(LAST_KEY)
    return v && v.length ? v : null
  } catch {
    return null
  }
}

/** Fallback for brand-new users with no watchlist and no prior selection:
 *  pick the top athlete in the user's first active sport so the default
 *  NIL Intelligence view renders real data instead of an empty dash. */
async function pickDefaultAthleteId(): Promise<string | null> {
  const sports = usePreferencesStore.getState().activeSports
  const primary = sports[0] ?? 'CFB'
  try {
    const rows = await searchAthletesFiltered({ sports: primary, limit: '1' })
    return rows[0]?.athlete_id ?? null
  } catch {
    return null
  }
}

export function useTerminalBootstrap() {
  useEffect(() => {
    void (async () => {
      await useAuthStore.getState().hydrate()
      const prefState = usePreferencesStore.getState()
      if (!prefState.hydrated) {
        await prefState.hydratePreferences()
      }
      await useWatchlistStore.getState().loadWatchlist()
      startWatchlistRefresh()
      void useAlertStore.getState().loadAlerts()
      startAlertPolling()

      const { activeAthleteId, setActiveAthlete } = useAthleteStore.getState()
      if (activeAthleteId) return

      const wl = useWatchlistStore.getState().athletes
      if (wl.length > 0) {
        void setActiveAthlete(wl[0].athlete_id)
        return
      }

      const last = readLastAthleteId()
      if (last) {
        void setActiveAthlete(last)
        return
      }

      const defaultId = await pickDefaultAthleteId()
      if (defaultId) {
        void setActiveAthlete(defaultId)
      }
    })()

    return () => {
      useFeedStore.getState().stopPoll()
    }
  }, [])
}

export function useFeedSync() {
  const id = useAthleteStore((s) => s.activeAthleteId)
  const loadFeed = useFeedStore((s) => s.loadFeed)
  const pollFeed = useFeedStore((s) => s.pollFeed)
  const stopPoll = useFeedStore((s) => s.stopPoll)

  useEffect(() => {
    if (!id) {
      stopPoll()
      return
    }
    void loadFeed(id)
    pollFeed(id)
    return () => stopPoll()
  }, [id, loadFeed, pollFeed, stopPoll])
}
