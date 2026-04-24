import { useEffect, useState } from 'react'
import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { getSessionToken } from '../../api/client'
import { usePreferencesStore } from '../../stores/preferencesStore'

/**
 * Runs inside ProtectedRoute. Loads preferences for the logged-in user and:
 *  - if onboarding is not yet complete → redirects to /onboarding
 *  - if the preferences call fails because there is no valid session → redirects to /login
 *  - in local-dev without a backend (VITE_USE_MOCKS=true or DEV build) stubs defaults so
 *    the Shell still renders for hacking.
 */
export function RequireOnboardingComplete() {
  const location = useLocation()
  const [ready, setReady] = useState(false)
  const [redirectTo, setRedirectTo] = useState<string | null>(null)
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
    if (!token) {
      setRedirectTo('/login')
      return
    }
    void (async () => {
      const p = await hydratePreferences()
      if (!p) {
        // Preferences call failed — most commonly because the JWT is invalid/expired.
        setRedirectTo('/login')
        return
      }
      if (!p.onboarding_completed_at) {
        setRedirectTo('/onboarding')
        return
      }
      setReady(true)
    })()
  }, [hydratePreferences])

  if (redirectTo && location.pathname !== redirectTo) {
    return <Navigate to={redirectTo} replace />
  }
  if (!ready) return null
  return <Outlet />
}
