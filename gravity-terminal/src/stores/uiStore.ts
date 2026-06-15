import { create } from 'zustand'
import {
  DEFAULT_SIMPLE_CONFIG,
  type CscConfigMode,
  type CscSimpleConfig,
} from '../lib/cscConfigPresets'
import type { CscReportParams } from '../types/reports'
import type { BrandMatchResult } from '../types/reports'

// Persistence keys for CSC configuration. Stored under a single
// versioned namespace so future schema changes can bump the version
// without colliding with stale user state.
const CSC_CONFIG_STORAGE_KEY = 'gravity.cscConfig.v1'

type PersistedCscConfig = {
  reportConfig?: CscReportParams
  cscConfigMode?: CscConfigMode
  cscSimpleConfig?: CscSimpleConfig
}

function readPersistedCscConfig(): PersistedCscConfig {
  if (typeof window === 'undefined') return {}
  try {
    const raw = window.localStorage.getItem(CSC_CONFIG_STORAGE_KEY)
    if (!raw) return {}
    const parsed = JSON.parse(raw)
    if (parsed && typeof parsed === 'object') return parsed as PersistedCscConfig
  } catch {
    // Corrupted storage: fall through to defaults rather than crashing
    // the whole UI on a single bad JSON parse.
  }
  return {}
}

function writePersistedCscConfig(state: PersistedCscConfig): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(CSC_CONFIG_STORAGE_KEY, JSON.stringify(state))
  } catch {
    // Storage may be full or disabled in private mode; ignore silently.
  }
}

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
export type MarketScanFilters = {
  position: string
  conference: string
}

export type UiStore = {
  activeSidebarItem: SidebarItem | null
  commandBarValue: string
  commandBarHistory: string[]
  commandBarHistoryIndex: number
  isReportModalOpen: boolean
  reportConfig: CscReportParams
  cscConfigMode: CscConfigMode
  cscSimpleConfig: CscSimpleConfig
  cscConfigOpen: boolean
  marketScanSub: MarketScanSub
  marketScanFilters: MarketScanFilters
  brandMatchSummary: string | null
  athleteCorpusEmpty: boolean
  brandMatchRefineToken: number
  brandMatchShortlist: BrandMatchResult[]
  brandMatchResultContext: {
    median_match_score: number | null
    median_nil_p50: number | null
    median_social_reach: number | null
    median_engagement_rate: number | null
    total_matches: number
  } | null
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
  setCscConfigMode: (mode: CscConfigMode) => void
  setCscSimpleConfig: (p: Partial<CscSimpleConfig>) => void
  setCscConfigOpen: (open: boolean) => void
  setMarketScanSub: (s: MarketScanSub) => void
  setMarketScanFilters: (next: Partial<MarketScanFilters>) => void
  resetMarketScanFilters: () => void
  setBrandMatchSummary: (s: string | null) => void
  setAthleteCorpusEmpty: (v: boolean) => void
  requestBrandMatchRefine: () => void
  setBrandMatchResultContext: (rows: BrandMatchResult[]) => void
  toggleBrandMatchShortlist: (row: BrandMatchResult) => void
  clearBrandMatchShortlist: () => void
  setCohortIds: (ids: string[]) => void
  setCscLockedFromAgent: (v: boolean) => void
}

const MAX_H = 50

function median(vals: number[]): number | null {
  if (!vals.length) return null
  const sorted = [...vals].sort((a, b) => a - b)
  const mid = Math.floor(sorted.length / 2)
  if (sorted.length % 2 === 1) return sorted[mid]
  return (sorted[mid - 1] + sorted[mid]) / 2
}

const PERSISTED_CONFIG = readPersistedCscConfig()

const DEFAULT_REPORT_CONFIG: CscReportParams = {
  comparables_count: 12,
  confidence_min: 0.75,
  csc_band_low_pct: 25,
  csc_band_high_pct: 75,
  verified_only: true,
}

export const useUiStore = create<UiStore>((set, get) => ({
  activeSidebarItem: null,
  commandBarValue: '',
  commandBarHistory: [],
  commandBarHistoryIndex: -1,
  isReportModalOpen: false,
  reportConfig: { ...DEFAULT_REPORT_CONFIG, ...(PERSISTED_CONFIG.reportConfig ?? {}) },
  cscConfigMode: PERSISTED_CONFIG.cscConfigMode ?? 'simple',
  cscSimpleConfig: { ...DEFAULT_SIMPLE_CONFIG, ...(PERSISTED_CONFIG.cscSimpleConfig ?? {}) },
  cscConfigOpen: false,
  marketScanSub: 'position',
  marketScanFilters: {
    position: '',
    conference: '',
  },
  brandMatchSummary: null,
  athleteCorpusEmpty: false,
  brandMatchRefineToken: 0,
  brandMatchShortlist: [],
  brandMatchResultContext: null,
  cohortIds: [],
  cscLockedFromAgent: false,

  setActiveSidebarItem: (item) => set({ activeSidebarItem: item }),
  setCommandBarValue: (v) => set({ commandBarValue: v }),
  setReportModalOpen: (v) => set({ isReportModalOpen: v }),
  setReportConfig: (p) => {
    const next = { ...get().reportConfig, ...p }
    set({ reportConfig: next })
    writePersistedCscConfig({
      reportConfig: next,
      cscConfigMode: get().cscConfigMode,
      cscSimpleConfig: get().cscSimpleConfig,
    })
  },
  setCscConfigMode: (mode) => {
    set({ cscConfigMode: mode })
    writePersistedCscConfig({
      reportConfig: get().reportConfig,
      cscConfigMode: mode,
      cscSimpleConfig: get().cscSimpleConfig,
    })
  },
  setCscSimpleConfig: (p) => {
    const next = { ...get().cscSimpleConfig, ...p }
    set({ cscSimpleConfig: next })
    writePersistedCscConfig({
      reportConfig: get().reportConfig,
      cscConfigMode: get().cscConfigMode,
      cscSimpleConfig: next,
    })
  },
  setCscConfigOpen: (open) => set({ cscConfigOpen: open }),
  setMarketScanSub: (s) => set({ marketScanSub: s }),
  setMarketScanFilters: (next) =>
    set({ marketScanFilters: { ...get().marketScanFilters, ...next } }),
  resetMarketScanFilters: () =>
    set({
      marketScanFilters: {
        position: '',
        conference: '',
      },
    }),
  setBrandMatchSummary: (s) => set({ brandMatchSummary: s }),
  setAthleteCorpusEmpty: (v) => set({ athleteCorpusEmpty: v }),
  requestBrandMatchRefine: () =>
    set((state) => ({ brandMatchRefineToken: state.brandMatchRefineToken + 1 })),
  setBrandMatchResultContext: (rows) =>
    set({
      brandMatchResultContext: {
        median_match_score: median(rows.map((r) => r.match_score).filter((x) => Number.isFinite(x))),
        median_nil_p50: median(
          rows
            .map((r) => {
              const lo = r.deal_range_low
              const hi = r.deal_range_high
              if (typeof lo !== 'number' || typeof hi !== 'number') return null
              return (lo + hi) / 2
            })
            .filter((x): x is number => typeof x === 'number' && Number.isFinite(x)),
        ),
        median_social_reach: median(
          rows
            .map((r) => r.social_combined_reach)
            .filter((x): x is number => typeof x === 'number' && Number.isFinite(x)),
        ),
        median_engagement_rate: median(
          rows
            .map((r) => r.instagram_engagement_rate)
            .filter((x): x is number => typeof x === 'number' && Number.isFinite(x)),
        ),
        total_matches: rows.length,
      },
    }),
  toggleBrandMatchShortlist: (row) =>
    set((state) => {
      const exists = state.brandMatchShortlist.some((x) => x.athlete_id === row.athlete_id)
      return {
        brandMatchShortlist: exists
          ? state.brandMatchShortlist.filter((x) => x.athlete_id !== row.athlete_id)
          : [...state.brandMatchShortlist, row],
      }
    }),
  clearBrandMatchShortlist: () => set({ brandMatchShortlist: [] }),
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
