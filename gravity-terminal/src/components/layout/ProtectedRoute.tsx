import { useEffect } from 'react'
import { Navigate, Outlet } from 'react-router-dom'
import { useAuthStore } from '../../stores/authStore'
import { getSessionToken } from '../../api/client'

/**
 * Guards every route inside Shell. Kicks off auth hydration immediately on
 * mount so it never deadlocks waiting for Shell (which is a child of Outlet).
 */
export function ProtectedRoute() {
  const hydrated = useAuthStore((s) => s.hydrated)
  const userId = useAuthStore((s) => s.userId)

  // Kick off hydration here so we don't deadlock waiting for Shell to mount
  useEffect(() => {
    if (!hydrated) {
      void useAuthStore.getState().hydrate()
    }
  }, [hydrated])

  const token = getSessionToken()
  const devMode =
    !token && (import.meta.env.VITE_USE_MOCKS === 'true' || import.meta.env.DEV)

  // Show nothing while auth resolves (happens in < 1 frame when no token)
  if (!hydrated) return null

  if (!userId && !devMode) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}
