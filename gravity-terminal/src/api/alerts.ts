import { mapAlertRow } from './adapters/athlete'
import { apiGet, apiPost } from './client'
import type { AlertRecord } from '../types/alerts'

export function getAlerts(userId: string, sportsCsv?: string | null) {
  const sp = new URLSearchParams({ user_id: userId })
  if (sportsCsv) sp.set('sports', sportsCsv)
  return apiGet<{ items: Record<string, unknown>[]; unread?: number }>(
    `alerts?${sp.toString()}`,
  ).then((r) =>
    (r.items ?? []).map((row) =>
      mapAlertRow(row, String(row.athlete_name ?? row.name ?? 'Athlete')),
    ),
  )
}

export function markAlertsRead(body: { alert_ids?: string[]; mark_all?: boolean }) {
  return apiPost<{ ok: boolean }>('alerts/mark-read', {
    alert_ids: body.alert_ids ?? [],
    mark_all: body.mark_all ?? false,
  })
}

export function isPersistedAlertId(id: string) {
  return !id.startsWith('live:')
}

export type { AlertRecord }
