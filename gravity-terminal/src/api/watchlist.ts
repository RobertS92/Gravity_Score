import { mapWatchlistAthleteRow } from './adapters/athlete'
import { apiGet, apiPost, apiDelete } from './client'

export function getWatchlist(userId: string) {
  return apiGet<{ athletes: Record<string, unknown>[] }>(
    `watchlist?user_id=${encodeURIComponent(userId)}`,
  ).then((r) => (r.athletes ?? []).map((row) => mapWatchlistAthleteRow(row)))
}

export function addToWatchlistApi(athleteId: string) {
  return apiPost<{ ok: boolean; athlete_id: string }>('watchlist/', { athlete_id: athleteId })
}

export function removeFromWatchlistApi(athleteId: string) {
  return apiDelete<{ ok: boolean }>(`watchlist/${athleteId}`)
}
