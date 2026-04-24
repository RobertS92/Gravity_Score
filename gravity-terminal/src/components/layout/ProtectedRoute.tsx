import { useEffect } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'
import { getSessionToken } from '../../api/client'

/**
 * Guards every route inside Shell. Kicks off auth hydration immediately on mount
 * so we don't deadlock waiting for Shell (which is a child of Outlet).
 *
 * In production: no JWT in localStorage → redirect to /login. Signup lives at
 * /onboarding which is a public route (reachable without a token).
 *
 * In local dev (vite dev or VITE_USE_MOCKS=true): authStore.hydrate() stubs a
 * DEFAULT_DEV_USER so the UI is usable without running the backend.
 */
export function ProtectedRoute() {
  const hydrated = useAuthStore((s) => s.hydrated)
  const userId = useAuthStore((s) => s.userId)

  useEffect(() => {
    if (!hydrated) {
      void useAuthStore.getState().hydrate()
    }
  }, [hydrated])

  if (!hydrated) return null

  const token = getSessionToken()
  const hasSession = !!token && !!userId

  // Local-dev convenience: no token but the store populated a fallback userId.
  // `vite build` sets import.meta.env.DEV=false so this never triggers in prod.
  const devFallbackActive = !token && !!userId &&
    (import.meta.env.VITE_USE_MOCKS === 'true' || import.meta.env.DEV)

  if (!hasSession && !devFallbackActive) {
    return <Navigate to="/login" replace />
  }
  return <Outlet />
}
