import { apiDelete, apiGet, apiPatch, apiPost } from './client'

export type CapSport = 'CFB' | 'NCAAB' | 'NCAAW'

export type UtilizationResponse = {
  org_id: string
  sport: string
  fiscal_year: number
  total_allocation_cents: number | null
  committed_cents: number
  third_party_cents: number
  incentive_exposure_cents: number
  utilization_pct: number | null
  remaining_cents: number | null
}

export type CapContract = {
  id: string
  athlete_id: string
  athlete_name?: string | null
  sport: string
  base_comp: number
  incentives: unknown[]
  third_party_flag: boolean
  payment_schedule: Record<string, unknown>
  fiscal_year_start: number
  eligibility_years_remaining?: number | null
  status: string
  scenario_id: string | null
}

export function fetchCapBudgets(orgId: string, sport: CapSport) {
  return apiGet<{ org_id: string; sport: string; budgets: unknown[] }>(`cap/budget/${orgId}/${sport}`)
}

export function fetchCapUtilization(orgId: string, sport: CapSport, year: number) {
  return apiGet<UtilizationResponse>(`cap/utilization/${orgId}/${sport}/${year}`)
}

export function fetchCapContracts(orgId: string, sport: CapSport) {
  return apiGet<{ contracts: CapContract[] }>(`cap/contracts/${orgId}/${sport}`)
}

export function fetchCapScenarios(orgId: string, sport: CapSport) {
  return apiGet<{ scenarios: unknown[] }>(`cap/org/${orgId}/scenarios/${sport}`)
}

export function createCapScenario(payload: { org_id: string; sport: CapSport; name: string }) {
  return apiPost<{ id: string; ok: boolean }>('cap/scenarios', payload)
}

export function fetchCapScenarioDetail(scenarioId: string) {
  return apiGet<{ scenario: Record<string, unknown>; contracts: CapContract[] }>(`cap/scenarios/${scenarioId}`)
}

export function fetchCapCompare(scenarioId: string) {
  return apiGet<Record<string, unknown>>(`cap/scenarios/${scenarioId}/compare`)
}

export function promoteCapScenario(scenarioId: string) {
  return apiPost<{ ok: boolean }>(`cap/scenarios/${scenarioId}/promote`, {})
}

export function fetchCapOutlook(orgId: string, sport: CapSport) {
  return apiGet<{
    org_id: string
    sport: string
    years: Array<{
      fiscal_year: number
      committed_cents: number
      incentive_exposure_cents: number
      headcount: number
      available_cap_cents: number | null
    }>
  }>(`cap/outlook/${orgId}/${sport}`)
}

export function fetchCapRollup(orgId: string) {
  return apiGet<{ org_id: string; sports: unknown[] }>(`cap/rollup/${orgId}`)
}

export function upsertCapBudget(payload: {
  org_id: string
  sport: CapSport
  fiscal_year: number
  total_allocation: number | null
  notes?: string | null
}) {
  return apiPost<{ id: string; ok: boolean }>('cap/budget', payload)
}

export function createCapContract(payload: Record<string, unknown>) {
  return apiPost<{ id: string; ok: boolean }>('cap/contracts', payload)
}

export function patchCapContract(contractId: string, payload: Record<string, unknown>) {
  return apiPatch<{ ok: boolean }>(`cap/contracts/${contractId}`, payload)
}

export function deleteCapContract(contractId: string) {
  return apiDelete<{ ok: boolean }>(`cap/contracts/${contractId}`)
}
