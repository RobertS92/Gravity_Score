import { create } from 'zustand'
import {
  type RosterAthleteRow,
  type RosterScored,
  type RosterSlot,
  deleteRoster,
  listRosters,
  saveRoster,
  scoreRosterPreview,
  type RosterSummary,
} from '../api/roster'

export type RosterStore = {
  // Current build (in-progress, not yet saved)
  name: string
  budget_usd: number
  slots: RosterSlot[]

  // Scored result from last preview/save
  scored: RosterScored | null

  // Saved roster list
  savedRosters: RosterSummary[]
  isLoadingSaved: boolean

  // Editing state
  isSaving: boolean
  isScoring: boolean
  error: string | null

  // Actions
  setName: (name: string) => void
  setBudget: (usd: number) => void
  addSlot: (athleteId: string) => void
  removeSlot: (athleteId: string) => void
  setCostOverride: (athleteId: string, cost: number | null) => void
  scorePreview: () => Promise<void>
  saveCurrentRoster: (id?: string) => Promise<void>
  loadSavedRosters: () => Promise<void>
  deleteSavedRoster: (id: string) => Promise<void>
  loadRosterById: (roster: RosterScored) => void
  reset: () => void
}

export const useRosterStore = create<RosterStore>((set, get) => ({
  name: 'My Roster',
  budget_usd: 1_000_000,
  slots: [],
  scored: null,
  savedRosters: [],
  isLoadingSaved: false,
  isSaving: false,
  isScoring: false,
  error: null,

  setName: (name) => set({ name }),
  setBudget: (budget_usd) => set({ budget_usd }),

  addSlot: (athleteId) => {
    if (get().slots.some((s) => s.athlete_id === athleteId)) return
    set({ slots: [...get().slots, { athlete_id: athleteId, nil_cost_override: null }] })
    void get().scorePreview()
  },

  removeSlot: (athleteId) => {
    set({ slots: get().slots.filter((s) => s.athlete_id !== athleteId) })
    void get().scorePreview()
  },

  setCostOverride: (athleteId, cost) => {
    set({
      slots: get().slots.map((s) =>
        s.athlete_id === athleteId ? { ...s, nil_cost_override: cost } : s,
      ),
    })
    void get().scorePreview()
  },

  scorePreview: async () => {
    const { name, budget_usd, slots } = get()
    if (!slots.length) {
      set({ scored: null })
      return
    }
    set({ isScoring: true, error: null })
    try {
      const result = await scoreRosterPreview({ name, budget_usd, slots })
      set({ scored: result, isScoring: false })
    } catch (e) {
      set({ isScoring: false, error: String(e) })
    }
  },

  saveCurrentRoster: async (id?: string) => {
    const { name, budget_usd, slots } = get()
    set({ isSaving: true, error: null })
    try {
      const result = await saveRoster({ id, name, budget_usd, slots })
      set({ scored: result, isSaving: false })
      await get().loadSavedRosters()
    } catch (e) {
      set({ isSaving: false, error: String(e) })
    }
  },

  loadSavedRosters: async () => {
    set({ isLoadingSaved: true })
    try {
      const rosters = await listRosters()
      set({ savedRosters: rosters, isLoadingSaved: false })
    } catch {
      set({ isLoadingSaved: false })
    }
  },

  deleteSavedRoster: async (id) => {
    try {
      await deleteRoster(id)
      set({ savedRosters: get().savedRosters.filter((r) => r.id !== id) })
    } catch {
      /* ignore */
    }
  },

  loadRosterById: (roster) => {
    set({
      name: roster.name,
      budget_usd: roster.budget_usd,
      slots: roster.athletes.map((a: RosterAthleteRow) => ({
        athlete_id: a.athlete_id,
        nil_cost_override: a.nil_cost_override ?? null,
      })),
      scored: roster,
    })
  },

  reset: () =>
    set({
      name: 'My Roster',
      budget_usd: 1_000_000,
      slots: [],
      scored: null,
      error: null,
    }),
}))
