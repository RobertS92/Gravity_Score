import { mapAlertRow } from './adapters/athlete'
import { apiGet } from './client'

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
