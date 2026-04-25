import { create } from 'zustand'
import {
  fetchFeed,
  fetchFeedCatalog,
  type FeedItem,
  type FeedSource,
  type VerificationLevel,
} from '../api/feed'

const DEFAULT_MIN_VERIFICATION: VerificationLevel = 'SINGLE_SOURCE'

const DEFAULT_CATEGORIES: string[] = [
  'NIL_DEAL',
  'TRANSFER',
  'INJURY',
  'NEWS',
  'AWARD',
  'RECRUITING',
  'PERFORMANCE',
  'ANNOUNCEMENT',
  'BUSINESS',
  'INCIDENT',
  'SCORE',
  'ROSTER',
]

const DEFAULT_SOURCES: FeedSource[] = ['watchlist', 'teams', 'general']

type State = {
  items: FeedItem[]
  isLoading: boolean
  isLoadingMore: boolean
  isHydrated: boolean
  error: string | null
  nextBefore: string | null
  hasMore: boolean

  // Filter state (persisted to localStorage)
  sources: Set<FeedSource>
  categories: Set<string>
  sports: string[]

  catalogCategories: string[]
  catalogSources: string[]
  catalogVerificationLevels: VerificationLevel[]

  /** Minimum trust level. SINGLE_SOURCE by default — drops UNVERIFIED + LOW_CONFIDENCE. */
  minVerification: VerificationLevel

  setSports: (sports: string[]) => void
  toggleSource: (s: FeedSource) => void
  toggleCategory: (c: string) => void
  setCategories: (cats: string[]) => void
  selectAllCategories: () => void
  clearCategories: () => void
  setMinVerification: (level: VerificationLevel) => void

  load: () => Promise<void>
  loadMore: () => Promise<void>
  loadCatalog: () => Promise<void>

  reset: () => void
}

const LS_KEY = 'gravity_live_feed_filters_v1'

type Persisted = {
  sources: FeedSource[]
  categories: string[]
  minVerification?: VerificationLevel
}

const VERIF_VALUES: VerificationLevel[] = [
  'OFFICIAL',
  'MULTI_SOURCE',
  'SINGLE_SOURCE',
  'LOW_CONFIDENCE',
  'UNVERIFIED',
]

function loadPersisted(): Persisted | null {
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw) as unknown
    if (!parsed || typeof parsed !== 'object') return null
    const p = parsed as Record<string, unknown>
    const mv = typeof p.minVerification === 'string' && VERIF_VALUES.includes(p.minVerification as VerificationLevel)
      ? (p.minVerification as VerificationLevel)
      : DEFAULT_MIN_VERIFICATION
    return {
      sources: Array.isArray(p.sources) ? (p.sources as FeedSource[]) : DEFAULT_SOURCES,
      categories: Array.isArray(p.categories) ? (p.categories as string[]) : [],
      minVerification: mv,
    }
  } catch {
    return null
  }
}

function savePersisted(state: {
  sources: Set<FeedSource>
  categories: Set<string>
  minVerification: VerificationLevel
}) {
  try {
    localStorage.setItem(
      LS_KEY,
      JSON.stringify({
        sources: Array.from(state.sources),
        categories: Array.from(state.categories),
        minVerification: state.minVerification,
      } satisfies Persisted),
    )
  } catch {
    /* ignore quota / private mode */
  }
}

const initial = (() => {
  const persisted = loadPersisted()
  return {
    sources: new Set<FeedSource>(persisted?.sources?.length ? persisted.sources : DEFAULT_SOURCES),
    categories: new Set<string>(persisted?.categories ?? []),
    minVerification: persisted?.minVerification ?? DEFAULT_MIN_VERIFICATION,
  }
})()

export const useLiveFeedStore = create<State>((set, get) => ({
  items: [],
  isLoading: false,
  isLoadingMore: false,
  isHydrated: false,
  error: null,
  nextBefore: null,
  hasMore: false,

  sources: initial.sources,
  categories: initial.categories,
  sports: [],
  minVerification: initial.minVerification,

  catalogCategories: DEFAULT_CATEGORIES,
  catalogSources: ['watchlist', 'teams', 'general'],
  catalogVerificationLevels: VERIF_VALUES,

  setSports: (sports: string[]) => {
    const cur = get().sports
    if (cur.length === sports.length && cur.every((s, i) => s === sports[i])) return
    set({ sports })
    void get().load()
  },

  toggleSource: (s: FeedSource) => {
    const next = new Set(get().sources)
    if (next.has(s)) next.delete(s)
    else next.add(s)
    if (next.size === 0) next.add(s)
    set({ sources: next })
    savePersisted({ sources: next, categories: get().categories, minVerification: get().minVerification })
    void get().load()
  },

  toggleCategory: (c: string) => {
    const next = new Set(get().categories)
    if (next.has(c)) next.delete(c)
    else next.add(c)
    set({ categories: next })
    savePersisted({ sources: get().sources, categories: next, minVerification: get().minVerification })
    void get().load()
  },

  setCategories: (cats: string[]) => {
    const next = new Set(cats)
    set({ categories: next })
    savePersisted({ sources: get().sources, categories: next, minVerification: get().minVerification })
    void get().load()
  },

  selectAllCategories: () => {
    const next = new Set<string>()
    set({ categories: next })
    savePersisted({ sources: get().sources, categories: next, minVerification: get().minVerification })
    void get().load()
  },

  clearCategories: () => {
    const next = new Set<string>()
    set({ categories: next })
    savePersisted({ sources: get().sources, categories: next, minVerification: get().minVerification })
    void get().load()
  },

  setMinVerification: (level: VerificationLevel) => {
    if (get().minVerification === level) return
    set({ minVerification: level })
    savePersisted({ sources: get().sources, categories: get().categories, minVerification: level })
    void get().load()
  },

  loadCatalog: async () => {
    try {
      const cat = await fetchFeedCatalog()
      set({
        catalogCategories: cat.categories?.length ? cat.categories : DEFAULT_CATEGORIES,
        catalogSources: cat.sources?.length ? cat.sources : ['watchlist', 'teams', 'general'],
        catalogVerificationLevels: cat.verification_levels?.length
          ? cat.verification_levels
          : VERIF_VALUES,
      })
    } catch {
      // catalog is non-critical; fall back to defaults already set
    }
  },

  load: async () => {
    const { sources, categories, sports, minVerification } = get()
    set({ isLoading: true, error: null })
    try {
      const res = await fetchFeed({
        sources: Array.from(sources),
        categories: categories.size ? Array.from(categories) : undefined,
        sports: sports.length ? sports : undefined,
        limit: 30,
        min_verification: minVerification,
      })
      set({
        items: res.items,
        nextBefore: res.next_before,
        hasMore: !!res.next_before,
        isLoading: false,
        isHydrated: true,
      })
    } catch (e) {
      set({
        isLoading: false,
        isHydrated: true,
        error: e instanceof Error ? e.message : 'Failed to load feed',
      })
    }
  },

  loadMore: async () => {
    const { nextBefore, sources, categories, sports, isLoadingMore, items, minVerification } = get()
    if (!nextBefore || isLoadingMore) return
    set({ isLoadingMore: true })
    try {
      const res = await fetchFeed({
        sources: Array.from(sources),
        categories: categories.size ? Array.from(categories) : undefined,
        sports: sports.length ? sports : undefined,
        before: nextBefore,
        limit: 30,
        min_verification: minVerification,
      })
      const seen = new Set(items.map((i) => i.id))
      const merged = [...items, ...res.items.filter((i) => !seen.has(i.id))]
      set({
        items: merged,
        nextBefore: res.next_before,
        hasMore: !!res.next_before,
        isLoadingMore: false,
      })
    } catch (e) {
      set({
        isLoadingMore: false,
        error: e instanceof Error ? e.message : 'Failed to load more',
      })
    }
  },

  reset: () =>
    set({
      items: [],
      isHydrated: false,
      error: null,
      nextBefore: null,
      hasMore: false,
    }),
}))
