import { useCallback, useEffect, useRef, useState } from 'react'
import { searchAthletesFiltered } from '../../api/athletes'
import type { AthleteRecord } from '../../types/athlete'
import { useWatchlistStore } from '../../stores/watchlistStore'
import { useRosterStore } from '../../stores/rosterStore'
import { formatScore } from '../../lib/formatters'
import styles from './WatchlistModal.module.css'

interface Props {
  onClose: () => void
  /** When set, clicking a result adds to roster instead of watchlist */
  mode?: 'watchlist' | 'roster'
}

const POSITIONS = ['QB', 'RB', 'WR', 'TE', 'OL', 'DL', 'LB', 'DB', 'K', 'PG', 'SG', 'SF', 'PF', 'C']
const CONFERENCES = ['SEC', 'Big Ten', 'Big 12', 'ACC', 'Pac-12', 'AAC', 'Mountain West']
const SPORTS = ['football', 'basketball', 'baseball']

type Filters = {
  q: string
  position: string
  conference: string
  sport: string
}

export function WatchlistModal({ onClose, mode = 'watchlist' }: Props) {
  const [filters, setFilters] = useState<Filters>({ q: '', position: '', conference: '', sport: '' })
  const [results, setResults] = useState<AthleteRecord[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const watchlist = useWatchlistStore((s) => s.athletes)
  const addToWatchlist = useWatchlistStore((s) => s.addToWatchlist)
  const addSlot = useRosterStore((s) => s.addSlot)
  const rosterSlots = useRosterStore((s) => s.slots)

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const doSearch = useCallback(async (f: Filters) => {
    setLoading(true)
    setError(null)
    try {
      const params: Record<string, string> = {}
      if (f.q) params.q = f.q
      if (f.position) params.position = f.position
      if (f.conference) params.conference = f.conference
      if (f.sport) params.sport = f.sport
      const r = await searchAthletesFiltered(params)
      setResults(r)
    } catch (e) {
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current)
    debounceRef.current = setTimeout(() => void doSearch(filters), 300)
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [filters, doSearch])

  // Search on mount
  useEffect(() => { void doSearch(filters) }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const isOnWatchlist = (id: string) => watchlist.some((a) => a.athlete_id === id)
  const isOnRoster = (id: string) => rosterSlots.some((s) => s.athlete_id === id)

  const handleAdd = (a: AthleteRecord) => {
    if (mode === 'roster') {
      addSlot(a.athlete_id)
    } else {
      void addToWatchlist(a.athlete_id)
    }
  }

  const alreadyAdded = (a: AthleteRecord) =>
    mode === 'roster' ? isOnRoster(a.athlete_id) : isOnWatchlist(a.athlete_id)

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        <header className={styles.header}>
          <span className={styles.title}>
            {mode === 'roster' ? 'ADD PLAYER TO ROSTER' : 'ADD TO WATCHLIST'}
          </span>
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
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
          <select
            className={styles.filterSelect}
            value={filters.position}
            onChange={(e) => setFilters((f) => ({ ...f, position: e.target.value }))}
          >
            <option value="">All Positions</option>
            {POSITIONS.map((p) => (
              <option key={p} value={p}>{p}</option>
            ))}
          </select>
          <select
            className={styles.filterSelect}
            value={filters.sport}
            onChange={(e) => setFilters((f) => ({ ...f, sport: e.target.value }))}
          >
            <option value="">All Sports</option>
            {SPORTS.map((s) => (
              <option key={s} value={s}>{s}</option>
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
            <div className={styles.statusMsg}>No results</div>
          )}
          {results.map((a) => {
            const added = alreadyAdded(a)
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
                    className={added ? styles.addedBtn : styles.addBtn}
                    disabled={added}
                    onClick={() => handleAdd(a)}
                  >
                    {added ? '✓ ADDED' : '+ ADD'}
                  </button>
                </div>
              </div>
            )
          })}
        </div>
      </div>
    </div>
  )
}
