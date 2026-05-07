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
  /** Latest gravity score components (joined server-side from athlete_gravity_scores).
   *  All optional — older deployments may not populate these. */
  gravity_score?: number | null
  brand_score?: number | null
  proof_score?: number | null
  velocity_score?: number | null
  risk_score?: number | null
}

export type CapScenario = {
  id: string
  name: string
  status: 'draft' | 'approved' | 'official' | 'promoted'
  aggregate_gravity_score?: number | null
  total_committed?: number | null
  total_risk_exposure?: number | null
  created_at?: string | null
  updated_at?: string | null
  promoted_at?: string | null
}

export type CapWorkflowQueue = {
  permissions: { can_view: boolean; can_edit: boolean; can_approve: boolean }
  pending: Array<{ id: string; name: string; status: string; created_at?: string | null; updated_at?: string | null }>
  events: Array<{ scenario_id: string | null; action: string; actor_user_id: string; notes?: string | null; created_at?: string | null }>
}

export type CapAuditEvent = {
  id: string
  user_id: string
  table_name: string
  record_id: string
  action: string
  old_values?: Record<string, unknown> | null
  new_values?: Record<string, unknown> | null
  created_at?: string | null
}

export type CapAlertsResponse = {
  derived: Array<{ type: string; severity: string; title: string; value: number }>
  events: Array<{
    id: string
    fiscal_year?: number | null
    alert_type: string
    severity: string
    title: string
    description?: string | null
    metric_value?: number | null
    threshold?: number | null
    created_at?: string | null
  }>
}

export type CapCashFlowResponse = {
  org_id: string
  sport: string
  fiscal_year: number
  months: Array<{
    month: string
    cap_cents: number
    third_party_cents: number
    incentive_cents: number
    total_cents: number
    cumulative_cents: number
  }>
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
  return apiGet<{ scenarios: CapScenario[] }>(`cap/org/${orgId}/scenarios/${sport}`)
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

export function approveCapScenario(scenarioId: string, notes?: string) {
  return apiPost<{ ok: boolean }>(`cap/scenarios/${scenarioId}/approve`, { notes: notes ?? null })
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

export function fetchCapWorkflowQueue(orgId: string, sport: CapSport) {
  return apiGet<CapWorkflowQueue>(`cap/workflow/queue/${orgId}/${sport}`)
}

export function fetchCapAuditLog(orgId: string, params: { sport?: CapSport; action?: string; table_name?: string; limit?: number } = {}) {
  const sp = new URLSearchParams()
  if (params.sport) sp.set('sport', params.sport)
  if (params.action) sp.set('action', params.action)
  if (params.table_name) sp.set('table_name', params.table_name)
  if (params.limit != null) sp.set('limit', String(params.limit))
  return apiGet<{ events: CapAuditEvent[] }>(`cap/audit/${orgId}${sp.toString() ? `?${sp.toString()}` : ''}`)
}

export function fetchCapAlerts(orgId: string, sport: CapSport) {
  return apiGet<CapAlertsResponse>(`cap/alerts/${orgId}/${sport}`)
}

export function fetchCapCashFlow(orgId: string, sport: CapSport, year: number) {
  return apiGet<CapCashFlowResponse>(`cap/cash-flow/${orgId}/${sport}/${year}`)
}

export function upsertCapPermissions(payload: {
  org_id: string
  user_id: string
  sport?: CapSport | null
  can_view: boolean
  can_edit: boolean
  can_approve: boolean
}) {
  return apiPost<{ ok: boolean; id: string }>('cap/permissions', payload)
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
