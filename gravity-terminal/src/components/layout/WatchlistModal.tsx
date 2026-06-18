import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { searchAthletesFilteredPaged } from '../../api/athletes'
import type { AthleteRecord } from '../../types/athlete'
import { useAthleteStore } from '../../stores/athleteStore'
import { usePreferencesStore } from '../../stores/preferencesStore'
import { useWatchlistStore } from '../../stores/watchlistStore'
import { formatScore } from '../../lib/formatters'
import styles from './WatchlistModal.module.css'

interface Props {
  onClose: () => void
}

const POSITIONS = ['QB', 'RB', 'WR', 'TE', 'OL', 'DL', 'LB', 'DB', 'K', 'PG', 'SG', 'SF', 'PF', 'C']
const CONFERENCES = ['SEC', 'Big Ten', 'Big 12', 'ACC', 'Pac-12', 'AAC', 'Mountain West']

/** Values must match `athletes.sport` (scrapers: cfb / ncaab_*; older DBs may use `mcbb` for MBB). */
const SPORT_OPTIONS: { label: string; value: string }[] = [
  { label: 'Football (CFB)', value: 'cfb' },
  { label: "Men's basketball", value: 'ncaab_mens' },
  { label: "Women's basketball", value: 'ncaab_womens' },
  { label: "Men's basketball (schema: mcbb)", value: 'mcbb' },
]
const PAGE_SIZE = 100

type Filters = {
  q: string
  position: string
  conference: string
  sport: string
}

export function WatchlistModal({ onClose }: Props) {
  const navigate = useNavigate()
  const [filters, setFilters] = useState<Filters>({ q: '', position: '', conference: '', sport: '' })
  const [results, setResults] = useState<AthleteRecord[]>([])
  const [total, setTotal] = useState<number>(0)
  const [hasMore, setHasMore] = useState(false)
  const [isLoadingMore, setIsLoadingMore] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [opening, setOpening] = useState<string | null>(null)

  const watchlist = useWatchlistStore((s) => s.athletes)
  const addToWatchlist = useWatchlistStore((s) => s.addToWatchlist)
  const setActiveAthlete = useAthleteStore((s) => s.setActiveAthlete)
  const activeSports = usePreferencesStore((s) => s.activeSports)
  const sportsCsv = activeSports.filter(Boolean).join(',')

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const doSearch = useCallback(async (f: Filters, offset = 0, append = false) => {
    if (append) setIsLoadingMore(true)
    else setLoading(true)
    setError(null)
    try {
      const params: Record<string, string> = {}
      if (f.q) params.q = f.q
      if (f.position) params.position_group = f.position
      if (f.conference) params.conference = f.conference
      if (f.sport) params.sport = f.sport
      else if (sportsCsv) params.sports = sportsCsv
      const page = await searchAthletesFilteredPaged(params, { limit: PAGE_SIZE, offset })
      setTotal(page.total)
      setHasMore(page.hasMore)
      if (append) {
        setResults((prev) => {
          const seen = new Set(prev.map((x) => x.athlete_id))
          const merged = [...prev]
          for (const next of page.athletes) {
            if (!seen.has(next.athlete_id)) merged.push(next)
          }
          return merged
        })
      } else {
        setResults(page.athletes)
      }
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e)
      setError(
        /load failed|failed to fetch|networkerror/i.test(message)
          ? 'Player search could not reach the Gravity API. Check the connection and retry.'
          : message,
      )
    } finally {
      if (append) setIsLoadingMore(false)
      else setLoading(false)
    }
  }, [sportsCsv])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    const hasSearch = Boolean(
      filters.q.trim() || filters.position || filters.conference || filters.sport,
    )
    if (!hasSearch) {
      setResults([])
      setTotal(0)
      setHasMore(false)
      setError(null)
      setLoading(false)
      return
    }
    debounceRef.current = setTimeout(() => void doSearch(filters, 0, false), 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [filters, doSearch, sportsCsv])

  const isOnWatchlist = (id: string) => watchlist.some((a) => a.athlete_id === id)

  const openAthlete = async (athleteId: string, destination: '/' | '/csc') => {
    setOpening(`${athleteId}:${destination}`)
    setError(null)
    await setActiveAthlete(athleteId)
    const loadError = useAthleteStore.getState().error
    if (loadError) {
      setError(loadError)
      setOpening(null)
      return
    }
    navigate(destination)
    onClose()
  }

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <header className={styles.header}>
          <span className={styles.title}>FIND PLAYER</span>
          <button type="button" className={styles.closeBtn} onClick={onClose}>
            ×
          </button>
        </header>

        <div className={styles.searchRow}>
          <input
            autoFocus
            type="text"
            className={styles.searchInput}
            placeholder="Search by name…"
            value={filters.q}
            onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))}
          />
        </div>

        <div className={styles.filterRow}>
          <select
            className={styles.filterSelect}
            value={filters.conference}
            onChange={(e) => setFilters((f) => ({ ...f, conference: e.target.value }))}
          >
            <option value="">All Conferences</option>
            {CONFERENCES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <select
            className={styles.filterSelect}
            value={filters.position}
            onChange={(e) => setFilters((f) => ({ ...f, position: e.target.value }))}
          >
            <option value="">All Positions</option>
            {POSITIONS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <select
            className={styles.filterSelect}
            value={filters.sport}
            onChange={(e) => setFilters((f) => ({ ...f, sport: e.target.value }))}
          >
            <option value="">All Sports</option>
            {SPORT_OPTIONS.map(({ label, value }) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
          {(filters.conference || filters.position || filters.sport || filters.q) && (
            <button
              type="button"
              className={styles.clearBtn}
              onClick={() => setFilters({ q: '', position: '', conference: '', sport: '' })}
            >
              Clear
            </button>
          )}
        </div>

        <div className={styles.resultsArea}>
          {loading && <div className={styles.statusMsg}>Searching…</div>}
          {error && <div className={styles.errorMsg}>{error}</div>}
          {!loading && results.length === 0 && !error && (
            <div className={styles.statusMsg}>
              {filters.q.trim() || filters.position || filters.conference || filters.sport
                ? 'No athletes match this search.'
                : 'Search for a player, then open their NIL Intelligence profile or CSC report.'}
            </div>
          )}
          {!loading && results.length > 0 && (
            <div className={styles.resultsMeta}>
              Showing {results.length} of {total}
            </div>
          )}
          {results.map((a) => {
            const added = isOnWatchlist(a.athlete_id)
            return (
              <div key={a.athlete_id} className={styles.resultRow}>
                <div className={styles.resultInfo}>
                  <span className={styles.resultName}>{a.name}</span>
                  <span className={styles.resultMeta}>
                    {[a.position, a.school, a.conference].filter(Boolean).join(' · ')}
                  </span>
                </div>
                <div className={styles.resultRight}>
                  <span className={styles.resultScore}>{formatScore(a.gravity_score ?? null)}</span>
                  <button
                    type="button"
                    className={styles.openBtn}
                    disabled={opening !== null}
                    onClick={() => void openAthlete(a.athlete_id, '/')}
                  >
                    {opening === `${a.athlete_id}:/` ? 'LOADING…' : 'NIL INTELLIGENCE'}
                  </button>
                  <button
                    type="button"
                    className={styles.openBtn}
                    disabled={opening !== null}
                    onClick={() => void openAthlete(a.athlete_id, '/csc')}
                  >
                    {opening === `${a.athlete_id}:/csc` ? 'LOADING…' : 'CSC REPORT'}
                  </button>
                  <button
                    type="button"
                    className={added ? styles.addedBtn : styles.addBtn}
                    disabled={added}
                    onClick={() => void addToWatchlist(a.athlete_id)}
                  >
                    {added ? '✓ WATCHING' : '+ WATCH'}
                  </button>
                </div>
              </div>
            )
          })}
          {!loading && hasMore && !error && (
            <div className={styles.loadMoreWrap}>
              <button
                type="button"
                className={styles.loadMoreBtn}
                onClick={() => void doSearch(filters, results.length, true)}
                disabled={isLoadingMore}
              >
                {isLoadingMore ? 'LOADING…' : `LOAD MORE (${PAGE_SIZE})`}
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
