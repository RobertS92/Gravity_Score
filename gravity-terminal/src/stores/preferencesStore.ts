import { create } from 'zustand'
import type { UserPreferences } from '../api/userPreferences'
import { fetchUserPreferences, patchUserPreferences } from '../api/userPreferences'

let sportPatchTimer: ReturnType<typeof setTimeout> | null = null

export type PreferencesState = {
  hydrated: boolean
  orgType: string | null
  activeSports: string[]
  initialTabKey: string | null
  rosterSeed: string | null
  athletesDefaultSort: string | null
  onboardingCompletedAt: string | null
  orgName: string | null
  displayName: string | null
  onboardingGoal: string | null
  /** One-shot: first Shell render uses this for default route */
  initialNavDone: boolean
  setInitialNavDone: () => void
  hydratePreferences: () => Promise<UserPreferences | null>
  setActiveSports: (sports: string[], persist?: boolean) => Promise<void>
  /** Updates UI immediately; persists after ~1s debounce (TopBar chips). */
  queueSportPreferencesPatch: (sports: string[]) => void
  applyFromApi: (p: UserPreferences) => void
}

function defaultSports(p: UserPreferences): string[] {
  const sp = p.sport_preferences
  if (sp && sp.length > 0) return [...sp]
  return ['CFB']
}

export const usePreferencesStore = create<PreferencesState>((set, get) => ({
  hydrated: false,
  orgType: null,
  activeSports: ['CFB'],
  initialTabKey: null,
  rosterSeed: null,
  athletesDefaultSort: null,
  onboardingCompletedAt: null,
  orgName: null,
  displayName: null,
  onboardingGoal: null,
  initialNavDone: false,

  setInitialNavDone: () => set({ initialNavDone: true }),

  applyFromApi: (p) => {
    set({
      orgType: p.org_type ?? null,
      activeSports: defaultSports(p),
      initialTabKey: p.default_dashboard_tab ?? null,
      rosterSeed: p.team_or_athlete_seed ?? null,
      athletesDefaultSort: p.athletes_default_sort ?? null,
      onboardingCompletedAt: p.onboarding_completed_at ?? null,
      orgName: p.org_name ?? null,
      displayName: p.display_name ?? null,
      onboardingGoal: p.onboarding_goal ?? null,
      hydrated: true,
    })
  },

  hydratePreferences: async () => {
    try {
      const p = await fetchUserPreferences()
      get().applyFromApi(p)
      return p
    } catch {
      set({ hydrated: true })
      return null
    }
  },

  setActiveSports: async (sports, persist = true) => {
    if (!sports.length) return
    set({ activeSports: sports })
    if (persist) {
      try {
        await patchUserPreferences({ sport_preferences: sports })
      } catch {
        /* ignore */
      }
    }
  },

  queueSportPreferencesPatch: (sports) => {
    if (!sports.length) return
    set({ activeSports: sports })
    if (sportPatchTimer) clearTimeout(sportPatchTimer)
    sportPatchTimer = setTimeout(() => {
      sportPatchTimer = null
      void patchUserPreferences({ sport_preferences: sports }).catch(() => {
        /* ignore */
      })
    }, 1000)
  },
}))

export function mapDashboardTabToPath(tab: string | null): string {
  switch (tab) {
    case 'roster':
      return '/cap'
    case 'market':
      return '/market-scan'
    case 'deals':
      return '/csc'
    case 'athletes':
    default:
      return '/'
  }
}

/** Static watchlist prompts by org_type (client-only). */
export function watchlistPromptForOrgType(orgType: string | null): string {
  switch (orgType) {
    case 'school':
    case 'nil_collective':
      return 'Add athletes to your watchlist to track NIL value changes.'
    case 'brand_agency':
      return 'Save athletes to track their Brand score movement.'
    case 'law_firm_agent':
      return 'Add athletes to your watchlist to monitor deal-relevant score shifts.'
    case 'insurance_finance':
      return 'Add athletes to your watchlist to monitor risk-related signals.'
    case 'media_research':
      return 'Add athletes to your watchlist for Gravity and market context.'
    default:
      return 'Add athletes to your watchlist to get started.'
  }
}
