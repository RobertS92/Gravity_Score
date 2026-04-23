import { apiGet, apiPost } from './client'

export function submitAthleteData(payload: {
  org_id: string
  athlete_id: string
  fields: Record<string, unknown>
  source_notes?: string | null
  run_verification?: boolean
}) {
  return apiPost<{ id: string; status: string; verification_results: unknown }>('data/submit', payload)
}

export function listDataSubmissions(orgId: string) {
  return apiGet<{ submissions: unknown[] }>(`data/submissions/${orgId}`)
}

export function computeOrgScore(orgId: string, athleteId: string) {
  return apiPost<Record<string, unknown>>(`data/org-score/${orgId}/${athleteId}`, {})
}
