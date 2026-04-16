import { formatNilMillions, formatScore } from '../../lib/formatters'
import type { AthleteRecord, ComparableRecord } from '../../types/athlete'
import styles from './ComparablesTable.module.css'

function formatDeltaDollar(n: number | null | undefined, self: boolean) {
  if (self) return '\u2014'
  if (n == null || Number.isNaN(n)) return '\u2014'
  const sign = n > 0 ? '+' : n < 0 ? '\u2212' : ''
  const v = Math.abs(n)
  const m = v / 1_000_000
  return `${sign}$${m.toFixed(1)}M`
}

export function ComparablesTable({
  athlete,
  comparables,
}: {
  athlete: AthleteRecord
  comparables: ComparableRecord[]
}) {
  const nDeals = athlete.verified_deals_count ?? comparables.reduce((a, c) => a + (c.verified_deal_count ?? 0), 0)
  const lo = athlete.gravity_percentile != null ? Math.max(1, athlete.gravity_percentile - 8) : null
  const hi = athlete.gravity_percentile != null ? Math.min(99, athlete.gravity_percentile + 6) : null
  const band =
    lo != null && hi != null ? `${lo}TH\u2013${hi}TH PCT` : '\u2014'

  const selfRow: ComparableRecord = {
    athlete_id: athlete.athlete_id,
    name: athlete.name,
    school: athlete.school ?? '',
    position: athlete.position ?? '',
    gravity_score: athlete.gravity_score,
    brand_score: athlete.brand_score,
    nil_valuation_consensus: athlete.nil_valuation_consensus,
    nil_delta_vs_subject: 0,
  }

  const rows = [selfRow, ...comparables]
  const insufficient = comparables.length < 4

  return (
    <section className={styles.box}>
      <h2 className={styles.title}>
        COMPARABLES — {nDeals || '\u2014'} VERIFIED DEALS IN RANGE · CSC BAND: {band}
      </h2>
      {insufficient && (
        <div className={styles.warnTitle}>
          INSUFFICIENT VERIFIED COMPARABLES — AGENT CAN ESTIMATE RANGE
        </div>
      )}
      <table className={styles.table}>
        <thead>
          <tr>
            <th className={styles.th}>ATHLETE</th>
            <th className={styles.thRight}>GS</th>
            <th className={styles.thRight}>BRAND</th>
            <th className={styles.thRight}>NIL EST.</th>
            <th className={styles.thRight}>DELTA</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => {
            const isSelf = c.athlete_id === athlete.athlete_id
            const d = c.nil_delta_vs_subject
            let deltaCls = styles.deltaDim
            if (!isSelf) {
              if (d != null && d > 0) deltaCls = styles.deltaPos
              else if (d != null && d < 0) deltaCls = styles.deltaNeg
            }
            return (
              <tr key={c.athlete_id} className={isSelf ? styles.selfRow : undefined}>
                <td className={styles.td}>
                  <div className={isSelf ? `${styles.nameMain} ${styles.selfName}` : styles.nameMain}>{c.name}</div>
                  <div className={styles.sub}>
                    {[c.school, c.position].filter(Boolean).join(' · ')}
                  </div>
                </td>
                <td className={styles.tdRight}>{formatScore(c.gravity_score)}</td>
                <td className={styles.tdRight}>{formatScore(c.brand_score)}</td>
                <td className={`${styles.tdRight} ${styles.nil}`}>
                  {formatNilMillions(c.nil_valuation_consensus)}
                </td>
                <td className={`${styles.tdRight} ${deltaCls}`}>
                  {formatDeltaDollar(isSelf ? null : c.nil_delta_vs_subject, isSelf)}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </section>
  )
}
