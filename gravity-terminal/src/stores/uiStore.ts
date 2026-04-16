import { create } from 'zustand'
import type { CscReportParams } from '../types/reports'

export type MainTab =
  | 'nil-intelligence'
  | 'csc-reports'
  | 'brand-match'
  | 'monitoring'
  | 'market-scan'

export type SidebarItem =
  | { section: 'watchlist'; id: string }
  | { section: 'csc'; id: string }
  | { section: 'research'; id: string }
  | { section: 'alerts'; id: string }

export type MarketScanSub = 'position' | 'school' | 'cohort'

export type UiStore = {
  activeSidebarItem: SidebarItem | null
  commandBarValue: string
  commandBarHistory: string[]
  commandBarHistoryIndex: number
  isReportModalOpen: boolean
  reportConfig: CscReportParams
  marketScanSub: MarketScanSub
  brandMatchSummary: string | null
  cohortIds: string[]
  /** When true, CSC view keeps current report until user regenerates or leaves */
  cscLockedFromAgent: boolean
  setActiveSidebarItem: (item: SidebarItem | null) => void
  setCommandBarValue: (v: string) => void
  pushHistory: (line: string) => void
  historyPrev: () => string | null
  historyNext: () => string | null
  setReportModalOpen: (v: boolean) => void
  setReportConfig: (p: Partial<CscReportParams>) => void
  setMarketScanSub: (s: MarketScanSub) => void
  setBrandMatchSummary: (s: string | null) => void
  setCohortIds: (ids: string[]) => void
  setCscLockedFromAgent: (v: boolean) => void
}

const MAX_H = 50

export const useUiStore = create<UiStore>((set, get) => ({
  activeSidebarItem: null,
  commandBarValue: '',
  commandBarHistory: [],
  commandBarHistoryIndex: -1,
  isReportModalOpen: false,
  reportConfig: {
    comparables_count: 12,
    confidence_min: 0.75,
    csc_band_low_pct: 25,
    csc_band_high_pct: 75,
    verified_only: true,
  },
  marketScanSub: 'position',
  brandMatchSummary: null,
  cohortIds: [],
  cscLockedFromAgent: false,

  setActiveSidebarItem: (item) => set({ activeSidebarItem: item }),
  setCommandBarValue: (v) => set({ commandBarValue: v }),
  setReportModalOpen: (v) => set({ isReportModalOpen: v }),
  setReportConfig: (p) => set({ reportConfig: { ...get().reportConfig, ...p } }),
  setMarketScanSub: (s) => set({ marketScanSub: s }),
  setBrandMatchSummary: (s) => set({ brandMatchSummary: s }),
  setCohortIds: (ids) => set({ cohortIds: ids }),
  setCscLockedFromAgent: (v) => set({ cscLockedFromAgent: v }),

  pushHistory: (line) => {
    const t = line.trim()
    if (!t) return
    const hist = [t, ...get().commandBarHistory.filter((x) => x !== t)].slice(0, MAX_H)
    set({ commandBarHistory: hist, commandBarHistoryIndex: -1 })
  },

  historyPrev: () => {
    const { commandBarHistory, commandBarHistoryIndex } = get()
    if (!commandBarHistory.length) return null
    const nextIdx = commandBarHistoryIndex < 0 ? 0 : Math.min(commandBarHistoryIndex + 1, commandBarHistory.length - 1)
    const line = commandBarHistory[nextIdx] ?? ''
    set({ commandBarHistoryIndex: nextIdx, commandBarValue: line })
    return line
  },

  historyNext: () => {
    const { commandBarHistory, commandBarHistoryIndex } = get()
    if (commandBarHistoryIndex <= 0) {
      set({ commandBarHistoryIndex: -1, commandBarValue: '' })
      return ''
    }
    const nextIdx = commandBarHistoryIndex - 1
    const line = commandBarHistory[nextIdx] ?? ''
    set({ commandBarHistoryIndex: nextIdx, commandBarValue: line })
    return line
  },
}))
