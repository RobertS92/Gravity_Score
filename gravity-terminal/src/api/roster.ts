import { apiDelete, apiGet, apiPost } from './client'

export interface RosterSlot {
  athlete_id: string
  nil_cost_override?: number | null
}

export interface RosterSummary {
  id: string
  name: string
  budget_usd: number
  slot_count: number
  created_at: string | null
  updated_at: string | null
}

export interface RosterAthleteRow {
  athlete_id: string
  name: string
  school: string
  position: string
  conference: string
  sport: string
  proof_score: number
  brand_score: number
  gravity_score: number
  nil_cost: number
  nil_cost_p10: number
  nil_cost_p90: number
  value_label: 'DEAL' | 'FAIR' | 'PREMIUM' | 'UNPRICED'
  nil_cost_override: number | null
}

export interface RosterScored {
  id?: string
  name: string
  budget_usd: number
  athletes: RosterAthleteRow[]
  talent_grade: string
  avg_proof: number
  total_spend: number
  efficiency_score: number
  position_depth: Record<string, number>
}

export function listRosters() {
  return apiGet<{ rosters: RosterSummary[] }>('roster/').then((r) => r.rosters ?? [])
}

export function getRoster(id: string) {
  return apiGet<RosterScored>(`roster/${id}`)
}

export function saveRoster(payload: {
  id?: string
  name: string
  budget_usd: number
  slots: RosterSlot[]
}) {
  return apiPost<RosterScored>('roster/', payload)
}

export function scoreRosterPreview(payload: {
  name: string
  budget_usd: number
  slots: RosterSlot[]
}) {
  return apiPost<RosterScored>('roster/score', payload)
}

export function deleteRoster(id: string) {
  return apiDelete<{ ok: boolean }>(`roster/${id}`)
}
