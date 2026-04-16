import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { getMarketScan, getMarketSchools } from '../../api/market'
import type { AthleteRecord } from '../../types/athlete'
import type { SchoolIndexRow } from '../../types/reports'
import { formatInteger, formatNilMillions, formatScore } from '../../lib/formatters'
import { useUiStore } from '../../stores/uiStore'
import styles from './MarketScanView.module.css'

const SPORT_LABELS: Record<string, string> = {
  cfb: 'CFB',
  ncaab_mens: 'MBB',
  ncaab_womens: 'WBB',
}

function progGColor(g: number | null | undefined) {
  if (g == null) return 'var(--text-muted)'
  if (g >= 75) return '#00ff88'
  if (g >= 60) return '#f0c844'
  return '#f07a44'
}

const CohortRadar = lazy(() => import('./CohortRadar'))

type SortKey = keyof AthleteRecord | 'name'

export function MarketScanView() {
  const sub = useUiStore((s) => s.marketScanSub)
  const setSub = useUiStore((s) => s.setMarketScanSub)
  const cohortIds = useUiStore((s) => s.cohortIds)

  const [rows, setRows] = useState<AthleteRecord[]>([])
  const [schools, setSchools] = useState<SchoolIndexRow[]>([])
  const [sortKey, setSortKey] = useState<SortKey>('gravity_score')
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc')
  const [schoolSport, setSchoolSport] = useState<string>('all')
  const [schoolSort, setSchoolSort] = useState<keyof SchoolIndexRow>('program_gravity_score')

  useEffect(() => {
    void getMarketScan({}).then(setRows)
    void getMarketSchools().then(setSchools)
  }, [])

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

  const cohortAthletes = useMemo(() => {
    const byId = new Map(rows.map((r) => [r.athlete_id, r]))
    const ids = cohortIds.length ? cohortIds : rows.slice(0, 3).map((r) => r.athlete_id)
    return ids.map((id) => byId.get(id)).filter(Boolean) as AthleteRecord[]
  }, [cohortIds, rows])

  const toggleSort = (k: SortKey) => {
    if (k === sortKey) setSortDir((d) => (d === 'desc' ? 'asc' : 'desc'))
    else {
      setSortKey(k)
      setSortDir('desc')
    }
  }

  return (
    <div className={styles.root}>
      <div className={styles.subBar}>
        <button type="button" className={sub === 'position' ? styles.subOn : styles.subOff} onClick={() => setSub('position')}>
          POSITION RANK
        </button>
        <button type="button" className={sub === 'school' ? styles.subOn : styles.subOff} onClick={() => setSub('school')}>
          SCHOOL INDEX
        </button>
        <button type="button" className={sub === 'cohort' ? styles.subOn : styles.subOff} onClick={() => setSub('cohort')}>
          COHORT COMPARE
        </button>
      </div>

      {sub === 'position' && (
        <div className={styles.tableWrap}>
          <table className={styles.table}>
            <thead>
              <tr>
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
              {sorted.map((a) => (
                <tr key={a.athlete_id}>
                  <td className={styles.td}>{a.name}</td>
                  <td className={styles.td}>{a.school ?? '\u2014'}</td>
                  <td className={styles.td}>{a.conference ?? '\u2014'}</td>
                  <td className={styles.tdR}>{formatScore(a.gravity_score)}</td>
                  <td className={styles.tdR}>{formatNilMillions(a.nil_valuation_consensus)}</td>
                  <td className={styles.tdR}>{formatScore(a.brand_score)}</td>
                  <td className={styles.tdR}>{formatScore(a.proof_score)}</td>
                  <td className={styles.tdR}>{formatScore(a.proximity_score)}</td>
                  <td className={styles.tdR}>{formatScore(a.velocity_score)}</td>
                  <td className={styles.tdR}>{formatScore(a.risk_score)}</td>
                </tr>
              ))}
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
                  <td className={styles.tdR}>{formatNilMillions(s.nil_market_size_estimate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {sub === 'cohort' && (
        <Suspense fallback={<div className={styles.muted}>Loading chart\u2026</div>}>
          <CohortRadar athletes={cohortAthletes} />
        </Suspense>
      )}
    </div>
  )
}
