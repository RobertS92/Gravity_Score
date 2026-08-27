import { useEffect, useMemo, useState } from 'react'
import { getAthlete } from '../../api/athletes'
import { getMarketScan, getMarketSchools, MARKET_SCAN_ROW_CAP } from '../../api/market'
import type { MarketScanRosterWindow } from '../../api/market'
import type { AthleteRecord } from '../../types/athlete'
import type { SchoolIndexRow } from '../../types/reports'
import { formatNilValue, formatScore } from '../../lib/formatters'
import { useAthleteStore } from '../../stores/athleteStore'
import { usePreferencesStore } from '../../stores/preferencesStore'
import { useUiStore } from '../../stores/uiStore'
import { useWatchlistStore } from '../../stores/watchlistStore'
import { TeamFavoriteStar } from '../shared/TeamFavoriteStar'
import CohortRadar from './CohortRadar'
import styles from './MarketScanView.module.css'

const SPORT_LABELS: Record<string, string> = {
  cfb: 'CFB',
  ncaab_mens: 'MBB',
  ncaab_womens: 'WBB',
}
const POSITION_GROUPS = ['QB', 'RB', 'WR', 'TE', 'OL', 'DL', 'LB', 'DB', 'K', 'PG', 'SG', 'SF', 'PF', 'C']
const CONFERENCES = ['SEC', 'Big Ten', 'Big 12', 'ACC', 'Pac-12', 'AAC', 'Mountain West']

function progGColor(g: number | null | undefined) {
  if (g == null) return 'var(--text-muted)'
  if (g >= 75) return '#00ff88'
  if (g >= 60) return '#f0c844'
  return '#f07a44'
}

type SortKey = keyof AthleteRecord | 'name'

export function MarketScanView() {
  const sub = useUiStore((s) => s.marketScanSub)
  const setSub = useUiStore((s) => s.setMarketScanSub)
  const marketScanFilters = useUiStore((s) => s.marketScanFilters)
  const setMarketScanFilters = useUiStore((s) => s.setMarketScanFilters)
  const resetMarketScanFilters = useUiStore((s) => s.resetMarketScanFilters)
  const cohortIds = useUiStore((s) => s.cohortIds)
  const setCohortIds = useUiStore((s) => s.setCohortIds)
  const toggleCohortId = useUiStore((s) => s.toggleCohortId)
  const watchlist = useWatchlistStore((s) => s.athletes)
  const activeSports = usePreferencesStore((s) => s.activeSports)
  const sportsCsv = useMemo(() => activeSports.filter(Boolean).join(','), [activeSports])
  const activeId = useAthleteStore((s) => s.activeAthleteId)
  const setActiveAthlete = useAthleteStore((s) => s.setActiveAthlete)

  const [rows, setRows] = useState<AthleteRecord[]>([])
  const [scanTotal, setScanTotal] = useState<number | null>(null)
  const [rosterWindow, setRosterWindow] = useState<MarketScanRosterWindow | null>(null)
  const [scanLoading, setScanLoading] = useState(true)
  const [scanError, setScanError] = useState<string | null>(null)
  const [schools, setSchools] = useState<SchoolIndexRow[]>([])
  const [fetchedById, setFetchedById] = useState<Record<string, AthleteRecord>>({})
  const [sortKey, setSortKey] = useState<SortKey>('gravity_score')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [schoolSport, setSchoolSport] = useState<string>('all')
  const [schoolSort, setSchoolSort] = useState<keyof SchoolIndexRow>('program_gravity_score')

  useEffect(() => {
    let cancelled = false
    const ac = new AbortController()
    setScanLoading(true)
    setScanError(null)
    setRows([])
    setScanTotal(null)
    setRosterWindow(null)
    void getMarketScan(
      {
        ...(sportsCsv ? { sports: sportsCsv } : {}),
        ...(marketScanFilters.position ? { position: marketScanFilters.position } : {}),
        ...(marketScanFilters.conference ? { conference: marketScanFilters.conference } : {}),
      },
      {
        signal: ac.signal,
        onPage: (r) => {
          if (cancelled) return
          setRows(r.athletes)
          setScanTotal(r.total)
          setRosterWindow(r.rosterWindow)
          setScanLoading(false)
        },
      },
    )
      .then((r) => {
        if (cancelled) return
        setRows(r.athletes)
        setScanTotal(r.total)
        setRosterWindow(r.rosterWindow)
      })
      .catch((e) => {
        if (cancelled || (e instanceof DOMException && e.name === 'AbortError')) return
        setScanError(e instanceof Error ? e.message : 'Market scan failed')
        setRows([])
        setScanTotal(0)
      })
      .finally(() => {
        if (!cancelled) setScanLoading(false)
      })
    void getMarketSchools()
      .then((list) => {
        if (!cancelled) setSchools(list)
      })
      .catch(() => {
        if (!cancelled) setSchools([])
      })
    return () => {
      cancelled = true
      ac.abort()
    }
  }, [sportsCsv, marketScanFilters.position, marketScanFilters.conference])

  const sorted = useMemo(() => {
    const out = [...rows]
    out.sort((a, b) => {
      const av = a[sortKey as keyof AthleteRecord]
      const bv = b[sortKey as keyof AthleteRecord]
      if (typeof av === 'number' && typeof bv === 'number') return sortDir === 'desc' ? bv - av : av - bv
      const as = String(av ?? '')
      const bs = String(bv ?? '')
      return sortDir === 'desc' ? bs.localeCompare(as) : as.localeCompare(bs)
    })
    return out
  }, [rows, sortKey, sortDir])

  const athleteIndex = useMemo(() => {
    const byId = new Map<string, AthleteRecord>()
    for (const r of rows) byId.set(r.athlete_id, r)
    for (const w of watchlist) byId.set(w.athlete_id, w)
    for (const a of Object.values(fetchedById)) byId.set(a.athlete_id, a)
    return byId
  }, [rows, watchlist, fetchedById])

  const previewIds = useMemo(() => {
    if (cohortIds.length) return cohortIds
    const fromWatch = watchlist.slice(0, 3).map((a) => a.athlete_id)
    if (fromWatch.length) return fromWatch
    return rows.slice(0, 3).map((r) => r.athlete_id)
  }, [cohortIds, watchlist, rows])

  const missingIds = useMemo(
    () => previewIds.filter((id) => !athleteIndex.has(id)),
    [previewIds, athleteIndex],
  )

  useEffect(() => {
    if (sub !== 'cohort' || missingIds.length === 0) return
    let cancelled = false
    void Promise.all(
      missingIds.map((id) =>
        getAthlete(id)
          .then((a) => a)
          .catch(() => null),
      ),
    ).then((fetched) => {
      if (cancelled) return
      const found = fetched.filter((a): a is AthleteRecord => a != null)
      if (found.length === 0) return
      setFetchedById((prev) => {
        let changed = false
        const next = { ...prev }
        for (const a of found) {
          if (next[a.athlete_id] !== a) {
            next[a.athlete_id] = a
            changed = true
          }
        }
        return changed ? next : prev
      })
    })
    return () => {
      cancelled = true
    }
  }, [sub, missingIds])

  const cohortAthletes = useMemo(
    () => previewIds.map((id) => athleteIndex.get(id)).filter(Boolean) as AthleteRecord[],
    [previewIds, athleteIndex],
  )

  const toggleSort = (k: SortKey) => {
    if (k === sortKey) setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'))
    else {
      setSortKey(k)
      setSortDir('desc')
    }
  }

  return (
    <div className={styles.root}>
      {sub === 'position' && (
        <div className={styles.muted}>
          {scanLoading && rows.length === 0
            ? 'Loading market…'
            : scanError
              ? scanError
              : scanTotal != null
                ? `Showing ${rows.length} of ${scanTotal}${
                    rows.length >= MARKET_SCAN_ROW_CAP && scanTotal > MARKET_SCAN_ROW_CAP
                      ? ` (display limited to first ${MARKET_SCAN_ROW_CAP} rows)`
                      : ''
                  }`
                : ''}
          {rosterWindow === 'stale_fallback' || rosterWindow === 'stale'
            ? ' · Roster verification is outside the live window — showing current-roster athletes.'
            : ''}
        </div>
      )}
      <div className={styles.subBar}>
        <button type="button" className={sub === 'position' ? styles.subOn : styles.subOff} onClick={() => setSub('position')}>
          POSITION RANK
        </button>
        <button type="button" className={sub === 'school' ? styles.subOn : styles.subOff} onClick={() => setSub('school')}>
          SCHOOL INDEX
        </button>
        <button type="button" className={sub === 'cohort' ? styles.subOn : styles.subOff} onClick={() => setSub('cohort')}>
          COHORT COMPARE{cohortIds.length ? ` (${cohortIds.length})` : ''}
        </button>
      </div>
      {sub === 'position' && (
        <div className={styles.filterBar}>
          <select
            className={styles.filterSelect}
            value={marketScanFilters.position}
            onChange={(e) => setMarketScanFilters({ position: e.target.value })}
          >
            <option value="">All Positions</option>
            {POSITION_GROUPS.map((p) => (
              <option key={p} value={p}>
                {p}
              </option>
            ))}
          </select>
          <select
            className={styles.filterSelect}
            value={marketScanFilters.conference}
            onChange={(e) => setMarketScanFilters({ conference: e.target.value })}
          >
            <option value="">All Conferences</option>
            {CONFERENCES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <button type="button" className={styles.clearBtn} onClick={resetMarketScanFilters}>
            Clear filters
          </button>
        </div>
      )}

      {sub === 'position' && (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
                <th className={styles.th} style={{ width: 36 }} aria-label="Compare" />
                {(
                  [
                    ['name', 'NAME'],
                    ['school', 'SCHOOL'],
                    ['conference', 'CONF'],
                    ['gravity_score', 'GS'],
                    ['nil_valuation_consensus', 'NIL'],
                    ['brand_score', 'B'],
                    ['proof_score', 'P'],
                    ['proximity_score', 'X'],
                    ['velocity_score', 'V'],
                    ['risk_score', 'R'],
                  ] as const
                ).map(([k, lab]) => (
                  <th key={k} className={styles.th}>
                    <button type="button" className={styles.sortBtn} onClick={() => toggleSort(k)}>
                      {lab}
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((a) => {
                const selected = cohortIds.includes(a.athlete_id)
                const active = a.athlete_id === activeId
                const rowClass = [
                  styles.row,
                  selected ? styles.rowSelected : '',
                  active ? styles.rowActive : '',
                ]
                  .filter(Boolean)
                  .join(' ')
                return (
                  <tr
                    key={a.athlete_id}
                    className={rowClass}
                    onClick={() => {
                      if (a.athlete_id) void setActiveAthlete(a.athlete_id)
                    }}
                  >
                    <td className={styles.td}>
                      <input
                        type="checkbox"
                        className={styles.compareCheck}
                        checked={selected}
                        disabled={!selected && cohortIds.length >= 5}
                        onClick={(e) => e.stopPropagation()}
                        onChange={() => toggleCohortId(a.athlete_id)}
                        aria-label={`Compare ${a.name}`}
                      />
                    </td>
                    <td className={styles.td}>{a.name}</td>
                    <td className={styles.td}>{a.school ?? '\u2014'}</td>
                    <td className={styles.td}>{a.conference ?? '\u2014'}</td>
                    <td className={styles.tdR}>{formatScore(a.gravity_score)}</td>
                    <td className={styles.tdR}>{formatNilValue(a.nil_valuation_consensus)}</td>
                    <td className={styles.tdR}>{formatScore(a.brand_score)}</td>
                    <td className={styles.tdR}>{formatScore(a.proof_score)}</td>
                    <td className={styles.tdR}>{formatScore(a.proximity_score)}</td>
                    <td className={styles.tdR}>{formatScore(a.velocity_score)}</td>
                    <td className={styles.tdR}>{formatScore(a.risk_score)}</td>
                  </tr>
                )
              })}
              {!scanLoading && !scanError && sorted.length === 0 && (
                <tr>
                  <td className={styles.td} colSpan={11}>
                    No current-roster athletes matched these filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {sub === 'school' && (
        <div className={styles.tableWrap}>
          <div className={styles.schoolFilters}>
            {(['all', 'cfb', 'ncaab_mens', 'ncaab_womens'] as const).map((sp) => (
              <button
                key={sp}
                type="button"
                className={schoolSport === sp ? styles.subOn : styles.subOff}
                onClick={() => setSchoolSport(sp)}
              >
                {sp === 'all' ? 'ALL' : SPORT_LABELS[sp]}
              </button>
            ))}
          </div>
          <table className={styles.table}>
            <thead>
              <tr>
                <th className={styles.th} style={{ width: 24 }} aria-label="Favorite" />
                <th className={styles.th}>SCHOOL</th>
                <th className={styles.th}>CONF</th>
                <th className={styles.th}>SPORT</th>
                <th
                  className={styles.thR}
                  style={{ cursor: 'pointer', textDecoration: schoolSort === 'program_gravity_score' ? 'underline' : undefined }}
                  onClick={() => setSchoolSort('program_gravity_score')}
                >
                  PROG G
                </th>
                <th
                  className={styles.thR}
                  style={{ cursor: 'pointer', textDecoration: schoolSort === 'avg_gravity_score' ? 'underline' : undefined }}
                  onClick={() => setSchoolSort('avg_gravity_score')}
                >
                  AVG G
                </th>
                <th className={styles.thR}># ATH</th>
                <th className={styles.th}>TOP ATHLETE</th>
                <th className={styles.thR}>NIL MKT</th>
              </tr>
            </thead>
            <tbody>
              {[...schools]
                .filter((s) => schoolSport === 'all' || s.sport === schoolSport)
                .sort((a, b) => {
                  const av = a[schoolSort] as number | null | undefined
                  const bv = b[schoolSort] as number | null | undefined
                  if (av == null && bv == null) return 0
                  if (av == null) return 1
                  if (bv == null) return -1
                  return bv - av
                })
                .map((s) => (
                <tr key={`${s.school}-${s.sport}`}>
                  <td className={styles.td}>
                    <TeamFavoriteStar teamId={s.team_id ?? null} teamName={s.school} />
                  </td>
                  <td className={styles.td}>{s.school}</td>
                  <td className={styles.td}>{s.conference ?? '\u2014'}</td>
                  <td className={styles.td}>{SPORT_LABELS[s.sport ?? ''] ?? s.sport ?? '\u2014'}</td>
                  <td className={styles.tdR}>
                    <span style={{ color: progGColor(s.program_gravity_score), fontWeight: 700 }}>
                      {s.program_gravity_score != null ? s.program_gravity_score.toFixed(1) : '\u2014'}
                    </span>
                  </td>
                  <td className={styles.tdR}>{formatScore(s.avg_gravity_score)}</td>
                  <td className={styles.tdR}>{s.athlete_count ?? '\u2014'}</td>
                  <td className={styles.td}>{s.top_athlete_name ?? '\u2014'}</td>
                  <td className={styles.tdR}>{formatNilValue(s.nil_market_size_estimate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {sub === 'cohort' && (
        <>
          <div className={styles.filterBar}>
            {watchlist.length > 0 &&
              watchlist.slice(0, 12).map((a) => (
                <button
                  key={a.athlete_id}
                  type="button"
                  className={cohortIds.includes(a.athlete_id) ? styles.subOn : styles.subOff}
                  onClick={() => toggleCohortId(a.athlete_id)}
                >
                  {a.name}
                </button>
              ))}
            {cohortIds.length > 0 && (
              <button type="button" className={styles.clearBtn} onClick={() => setCohortIds([])}>
                Clear selection
              </button>
            )}
            {watchlist.length === 0 && cohortIds.length === 0 && (
              <span className={styles.muted} style={{ padding: 0 }}>
                Check athletes on Position Rank, or add names to your watchlist, to pin a comparison.
              </span>
            )}
          </div>
          {cohortAthletes.length === 0 ? (
            <div className={styles.muted}>
              Select up to 5 athletes from Position Rank or your watchlist to compare Brand, Proof, Proximity, Velocity, and Risk.
            </div>
          ) : (
            <>
              {!cohortIds.length && (
                <div className={styles.muted}>
                  Previewing {cohortAthletes.map((a) => a.name).join(', ')}. Pin athletes on Position Rank or the chips above.
                </div>
              )}
              <CohortRadar athletes={cohortAthletes} />
            </>
          )}
        </>
      )}
    </div>
  )
}
