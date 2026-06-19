import { useEffect } from 'react'
import { searchAthletesFiltered } from '../api/athletes'
import { useAthleteStore } from '../stores/athleteStore'
import { useAuthStore } from '../stores/authStore'
import { useFeedStore } from '../stores/feedStore'
import { useLiveFeedStore } from '../stores/liveFeedStore'
import { usePreferencesStore } from '../stores/preferencesStore'
import { useTeamFavoritesStore } from '../stores/teamFavoritesStore'
import { useUiStore } from '../stores/uiStore'
import { useWatchlistStore, startWatchlistRefresh } from '../stores/watchlistStore'
import { useAlertStore, startAlertPolling, stopAlertPolling } from '../stores/alertStore'

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
    const fresh = await searchAthletesFiltered({ sports: primary, limit: '1' })
    if (fresh[0]?.athlete_id) return fresh[0].athlete_id

    const available = await searchAthletesFiltered({
      sports: primary,
      limit: '1',
      include_stale_roster: 'true',
    })
    return available[0]?.athlete_id ?? null
  } catch {
    return null
  }
}

export function useTerminalBootstrap() {
  useEffect(() => {
    void (async () => {
      const athleteState = useAthleteStore.getState()
      athleteState.setInitialLoading(true)
      useUiStore.getState().setAthleteCorpusEmpty(false)

      if (!useAuthStore.getState().hydrated) {
        await useAuthStore.getState().hydrate()
      }

      const prefState = usePreferencesStore.getState()
      const preferencesReady = prefState.hydrated
        ? Promise.resolve()
        : prefState.hydratePreferences().then(() => undefined)

      // Restore the last profile first so repeat visits can render from the
      // local bundle cache while secondary dashboard data loads in parallel.
      const last = readLastAthleteId()
      if (last) {
        await athleteState.setActiveAthlete(last)
        if (useAthleteStore.getState().activeAthlete) {
          void preferencesReady
          void useWatchlistStore.getState().loadWatchlist()
          startWatchlistRefresh()
          void useAlertStore.getState().loadAlerts()
          startAlertPolling()
          void useTeamFavoritesStore.getState().load()
          void useLiveFeedStore.getState().loadCatalog()
          return
        }
      }

      await preferencesReady
      await useWatchlistStore.getState().loadWatchlist()
      startWatchlistRefresh()
      void useAlertStore.getState().loadAlerts()
      startAlertPolling()
      void useTeamFavoritesStore.getState().load()
      void useLiveFeedStore.getState().loadCatalog()

      const { activeAthleteId, setActiveAthlete } = useAthleteStore.getState()
      if (activeAthleteId && useAthleteStore.getState().activeAthlete) return

      const wl = useWatchlistStore.getState().athletes
      if (wl.length > 0) {
        await setActiveAthlete(wl[0].athlete_id)
        if (useAthleteStore.getState().activeAthlete) return
      }

      const defaultId = await pickDefaultAthleteId()
      if (defaultId) {
        await setActiveAthlete(defaultId)
        if (useAthleteStore.getState().activeAthlete) return
      }

      useAthleteStore.getState().setInitialLoading(false)
      useUiStore.getState().setAthleteCorpusEmpty(true)
    })()

    return () => {
      useFeedStore.getState().stopPoll()
      stopAlertPolling()
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
