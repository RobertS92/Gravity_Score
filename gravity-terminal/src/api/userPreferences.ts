import { apiGet, apiPatch } from './client'

export type UserPreferences = {
  org_type: string | null
  sport_preferences: string[]
  org_name: string | null
  team_or_athlete_seed: string | null
  default_dashboard_tab: string | null
  athletes_default_sort: string | null
  onboarding_completed_at: string | null
  display_name?: string | null
  onboarding_goal?: string | null
}

export function fetchUserPreferences() {
  return apiGet<UserPreferences>('user/preferences')
}

export function patchUserPreferences(body: Partial<UserPreferences> & Record<string, unknown>) {
  return apiPatch<UserPreferences>('user/preferences', body)
}
