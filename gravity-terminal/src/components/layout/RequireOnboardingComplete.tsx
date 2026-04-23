import { useEffect, useState } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { getSessionToken } from '../../api/client'
import { usePreferencesStore } from '../../stores/preferencesStore'

/**
 * After JWT auth: load user preferences; send incomplete users to /onboarding.
 * Wraps Shell routes only (sibling route /onboarding is outside this layout).
 */
export function RequireOnboardingComplete() {
  const location = useLocation()
  const [ready, setReady] = useState(false)
  const [redirectOnboarding, setRedirectOnboarding] = useState(false)
  const hydratePreferences = usePreferencesStore((s) => s.hydratePreferences)

  useEffect(() => {
    const token = getSessionToken()
    const devNoToken =
      !token && (import.meta.env.VITE_USE_MOCKS === 'true' || import.meta.env.DEV)
    if (devNoToken) {
      usePreferencesStore.getState().applyFromApi({
        org_type: 'school',
        sport_preferences: ['CFB'],
        org_name: null,
        team_or_athlete_seed: null,
        default_dashboard_tab: 'roster',
        athletes_default_sort: null,
        onboarding_completed_at: new Date().toISOString(),
        display_name: 'Demo',
        onboarding_goal: null,
      })
      setReady(true)
      return
    }
    void (async () => {
      const p = await hydratePreferences()
      if (!p) {
        setReady(true)
        return
      }
      if (!p.onboarding_completed_at) {
        setRedirectOnboarding(true)
        return
      }
      setReady(true)
    })()
  }, [hydratePreferences])

  if (redirectOnboarding && location.pathname !== '/onboarding') {
    return <Navigate to="/onboarding" replace />
  }
  if (!ready) return null
  return <Outlet />
}
