import { mapAlertRow } from './adapters/athlete'
import { apiGet } from './client'

export function getAlerts(userId: string) {
  return apiGet<{ items: Record<string, unknown>[]; unread?: number }>(
    `alerts?user_id=${encodeURIComponent(userId)}`,
  ).then((r) =>
    (r.items ?? []).map((row) =>
      mapAlertRow(row, String(row.athlete_name ?? row.name ?? 'Athlete')),
    ),
  )
}
