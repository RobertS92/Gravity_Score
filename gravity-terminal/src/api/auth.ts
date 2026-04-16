import { apiGet, apiPost } from './client'

export type AuthMe = {
  user_id: string
  email?: string | null
  role?: string | null
  organization?: string | null
}

export function fetchMe() {
  return apiGet<AuthMe>('auth/me')
}

export function loginWithEmail(email: string, password: string) {
  return apiPost<{ access_token: string; token_type: string; user_id: string; email?: string }>(
    'auth/login',
    { email, password },
  )
}
