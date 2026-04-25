import { create } from 'zustand'
import {
  addTeamFavorite,
  listTeamFavorites,
  removeTeamFavorite,
  type TeamFavorite,
} from '../api/teamFavorites'

type TeamFavoritesState = {
  teams: TeamFavorite[]
  isLoading: boolean
  isHydrated: boolean
  error: string | null
  load: () => Promise<void>
  add: (teamId: string) => Promise<void>
  remove: (teamId: string) => Promise<void>
  isFavorite: (teamId: string) => boolean
  reset: () => void
}

export const useTeamFavoritesStore = create<TeamFavoritesState>((set, get) => ({
  teams: [],
  isLoading: false,
  isHydrated: false,
  error: null,

  reset: () => set({ teams: [], isHydrated: false, error: null }),

  load: async () => {
    set({ isLoading: true, error: null })
    try {
      const teams = await listTeamFavorites()
      set({ teams, isHydrated: true, isLoading: false })
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to load team favorites'
      set({ isLoading: false, error: msg, isHydrated: true })
    }
  },

  add: async (teamId: string) => {
    if (get().isFavorite(teamId)) return
    try {
      const team = await addTeamFavorite(teamId)
      set((s) => ({
        teams: s.teams.some((t) => t.team_id === team.team_id)
          ? s.teams
          : [team, ...s.teams],
        error: null,
      }))
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to add team favorite'
      set({ error: msg })
      throw e
    }
  },

  remove: async (teamId: string) => {
    const prev = get().teams
    set({ teams: prev.filter((t) => t.team_id !== teamId), error: null })
    try {
      await removeTeamFavorite(teamId)
    } catch (e) {
      set({ teams: prev, error: e instanceof Error ? e.message : 'Failed to remove' })
      throw e
    }
  },

  isFavorite: (teamId: string) => get().teams.some((t) => t.team_id === teamId),
}))
