import { create } from 'zustand'
import { fetchMe } from '../api/auth'
import { getSessionToken, setSessionToken } from '../api/client'

const ENV_USER = (import.meta.env.VITE_TERMINAL_USER_ID as string | undefined)?.trim() || ''
const DEFAULT_DEV_USER = '00000000-0000-4000-8000-000000000001'

// Local-only fallback so `npm run dev` without a backend still works as a demo.
// In production (`vite build`) `import.meta.env.DEV === false` and this is never used.
function devFallbackUserId(): string | null {
  if (ENV_USER) return ENV_USER
  if (import.meta.env.DEV || import.meta.env.VITE_USE_MOCKS === 'true') return DEFAULT_DEV_USER
  return null
}

export type AuthStore = {
  userId: string | null
  email: string | null
  role: string | null
  organizationId: string | null
  organizationSlug: string | null
  coachSports: string[]
  hydrated: boolean
  hydrate: () => Promise<void>
  /** Seed the store immediately after /auth/register or /auth/login so the
   *  first render after navigation is authenticated (no race vs. fetchMe). */
  applySessionFromAuth: (args: {
    access_token: string
    user_id: string
    email?: string | null
    role?: string | null
  }) => void
  clearSession: () => void
}

export const useAuthStore = create<AuthStore>((set) => ({
  userId: null,
  email: null,
  role: null,
  organizationId: null,
  organizationSlug: null,
  coachSports: [],
  hydrated: false,

  hydrate: async () => {
    const token = getSessionToken()
    if (!token) {
      set({
        userId: devFallbackUserId(),
        email: null,
        role: null,
        organizationId: null,
        organizationSlug: null,
        coachSports: [],
        hydrated: true,
      })
      return
    }
    try {
      const me = await fetchMe()
      set({
        userId: me.user_id,
        email: me.email ?? null,
        role: me.role ?? null,
        organizationId: me.organization_id ?? null,
        organizationSlug: me.organization_slug ?? null,
        coachSports: me.coach_sports ?? [],
        hydrated: true,
      })
    } catch {
      // Token invalid/expired — clear it so the user isn't stuck on the
      // Shell waiting for /me to succeed. The router will redirect to /login.
      setSessionToken('')
      set({
        userId: devFallbackUserId(),
        email: null,
        role: null,
        organizationId: null,
        organizationSlug: null,
        coachSports: [],
        hydrated: true,
      })
    }
  },

  applySessionFromAuth: ({ access_token, user_id, email, role }) => {
    setSessionToken(access_token)
    set({
      userId: user_id,
      email: email ?? null,
      role: role ?? null,
      organizationId: null,
      organizationSlug: null,
      coachSports: [],
      hydrated: true,
    })
  },

  clearSession: () => {
    setSessionToken('')
    set({
      userId: null,
      email: null,
      role: null,
      organizationId: null,
      organizationSlug: null,
      coachSports: [],
      hydrated: true,
    })
  },
}))

/**
 * Current user's UUID for API calls scoped to `?user_id=`.
 * Returns '' when unauthenticated — callers must treat '' as "skip the API call".
 */
export function getTerminalUserId(): string {
  const s = useAuthStore.getState()
  if (s.userId) return s.userId
  return devFallbackUserId() ?? ''
}
