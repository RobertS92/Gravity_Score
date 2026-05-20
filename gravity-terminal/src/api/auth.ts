import { apiGet, apiPost } from './client'

export type AuthMe = {
  user_id: string
  email?: string | null
  role?: string | null
  organization?: string | null
  organization_id?: string | null
  organization_slug?: string | null
  coach_sports?: string[]
  org_type?: string | null
  display_name?: string | null
  onboarding_completed_at?: string | null
}

export function fetchMe() {
  return apiGet<AuthMe>('auth/me')
}

export function loginWithEmail(email: string, password?: string) {
  const body: Record<string, string> = { email: email.trim().toLowerCase() }
  if (password) body.password = password
  return apiPost<{ access_token: string; token_type: string; user_id: string; email?: string }>(
    'auth/login',
    body,
  )
}

export function registerAccount(body: { email: string; password: string; display_name: string }) {
  return apiPost<{ access_token: string; token_type: string; user_id: string; email?: string }>(
    'auth/register',
    body,
  )
}

export function completeOnboarding(body: {
  org_type: string
  sport_preferences: string[]
  org_name?: string | null
  team_or_athlete_seed?: string | null
  onboarding_goal?: string | null
}) {
  return apiPost<{
    user_id: string
    email?: string
    role?: string
    org_type?: string | null
    sport_preferences?: string[]
    org_name?: string | null
    team_or_athlete_seed?: string | null
    default_dashboard_tab?: string | null
    athletes_default_sort?: string | null
    onboarding_completed_at?: string | null
    display_name?: string | null
    onboarding_goal?: string | null
  }>('auth/onboarding', body)
}

export function forgotPassword(email: string) {
  return apiPost<{ ok: boolean; message: string; debug_reset_token?: string; debug_reset_link?: string }>(
    'auth/forgot-password',
    { email: email.trim().toLowerCase() },
  )
}

export function resetPassword(token: string, password: string) {
  return apiPost<{ ok: boolean; message: string }>('auth/reset-password', {
    token: token.trim(),
    password,
  })
}
