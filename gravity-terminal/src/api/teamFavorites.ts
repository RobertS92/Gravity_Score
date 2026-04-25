import { apiDelete, apiGet, apiPost } from './client'

export type TeamFavorite = {
  team_id: string
  school_name: string | null
  conference: string | null
  sport: string | null
  created_at: string | null
}

type ListResponse = { teams: TeamFavorite[] }

export async function listTeamFavorites(): Promise<TeamFavorite[]> {
  const res = await apiGet<ListResponse>('team-favorites')
  return res.teams ?? []
}

export async function addTeamFavorite(teamId: string): Promise<TeamFavorite> {
  return apiPost<TeamFavorite>('team-favorites', { team_id: teamId })
}

export async function removeTeamFavorite(teamId: string): Promise<{ ok: true }> {
  return apiDelete<{ ok: true }>(`team-favorites/${teamId}`)
}
