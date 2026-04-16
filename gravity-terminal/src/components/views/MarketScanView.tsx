import { lazy, Suspense, useEffect, useMemo, useState } from 'react'
import { getMarketScan, getMarketSchools } from '../../api/market'
import type { AthleteRecord } from '../../types/athlete'
import type { SchoolIndexRow } from '../../types/reports'
import { formatInteger, formatNilMillions, formatScore } from '../../lib/formatters'
import { useUiStore } from '../../stores/uiStore'
import styles from './MarketScanView.module.css'

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
          <table className={styles.table}>
            <thead>
              <tr>
                <th className={styles.th}>SCHOOL</th>
                <th className={styles.th}>CONF</th>
                <th className={styles.thR}>AVG GS</th>
                <th className={styles.thR}>WL</th>
                <th className={styles.th}>TOP</th>
                <th className={styles.thR}>NIL MKT</th>
              </tr>
            </thead>
            <tbody>
              {schools.map((s) => (
                <tr key={s.school}>
                  <td className={styles.td}>{s.school}</td>
                  <td className={styles.td}>{s.conference ?? '\u2014'}</td>
                  <td className={styles.tdR}>{formatScore(s.avg_gravity_score)}</td>
                  <td className={styles.tdR}>{formatInteger(s.watchlisted_count)}</td>
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
