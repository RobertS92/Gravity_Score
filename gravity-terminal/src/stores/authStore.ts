import { create } from 'zustand'
import { fetchMe } from '../api/auth'
import { getSessionToken } from '../api/client'

const ENV_USER = (import.meta.env.VITE_TERMINAL_USER_ID as string | undefined)?.trim() || ''
const DEFAULT_DEV_USER = '00000000-0000-4000-8000-000000000001'

export type AuthStore = {
  userId: string | null
  email: string | null
  hydrated: boolean
  hydrate: () => Promise<void>
}

export const useAuthStore = create<AuthStore>((set) => ({
  userId: null,
  email: null,
  hydrated: false,

  hydrate: async () => {
    const token = getSessionToken()
    if (!token) {
      set({
        userId: ENV_USER || DEFAULT_DEV_USER,
        email: null,
        hydrated: true,
      })
      return
    }
    try {
      const me = await fetchMe()
      set({
        userId: me.user_id,
        email: me.email ?? null,
        hydrated: true,
      })
    } catch {
      set({
        userId: ENV_USER || DEFAULT_DEV_USER,
        email: null,
        hydrated: true,
      })
    }
  },
}))

export function getTerminalUserId(): string {
  const s = useAuthStore.getState()
  if (s.userId) return s.userId
  return ENV_USER || DEFAULT_DEV_USER
}
