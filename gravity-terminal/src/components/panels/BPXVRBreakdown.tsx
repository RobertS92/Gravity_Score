import { formatScore } from '../../lib/formatters'
import type { AthleteRecord } from '../../types/athlete'
import styles from './BPXVRBreakdown.module.css'

const ROWS: {
  letter: string
  key: 'brand_score' | 'proof_score' | 'proximity_score' | 'velocity_score' | 'risk_score'
  fill: string
  driver: keyof NonNullable<AthleteRecord['shap_drivers']>
}[] = [
  { letter: 'B', key: 'brand_score', fill: styles.fillB, driver: 'brand' },
  { letter: 'P', key: 'proof_score', fill: styles.fillP, driver: 'proof' },
  { letter: 'X', key: 'proximity_score', fill: styles.fillX, driver: 'proximity' },
  { letter: 'V', key: 'velocity_score', fill: styles.fillV, driver: 'velocity' },
  { letter: 'R', key: 'risk_score', fill: styles.fillR, driver: 'risk' },
]

export function BPXVRBreakdown({ athlete }: { athlete: AthleteRecord }) {
  return (
    <section className={styles.box}>
      <h2 className={styles.title}>COMPONENT BREAKDOWN — SHAP ATTRIBUTION</h2>
      {ROWS.map((r) => {
        const v = athlete[r.key]
        const pct = v == null ? 0 : Math.min(100, Math.max(0, v))
        const ctx = athlete.shap_drivers?.[r.driver] ?? '\u2014'
        return (
          <div key={r.letter} className={styles.row}>
            <span className={styles.letter}>{r.letter}</span>
            <div className={styles.track}>
              <div className={`${styles.fill} ${r.fill}`} style={{ width: `${pct}%` }} />
            </div>
            <span className={styles.score}>{formatScore(v)}</span>
            <span className={styles.ctx} title={ctx}>
              {ctx}
            </span>
          </div>
        )
      })}
    </section>
  )
}
