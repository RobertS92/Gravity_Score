import { formatDelta, formatScore } from '../../lib/formatters'
import type { AthleteRecord, ShapFactor } from '../../types/athlete'
import styles from './BPXVRBreakdown.module.css'

const ROWS: {
  letter: string
  label: string
  key: 'brand_score' | 'proof_score' | 'proximity_score' | 'velocity_score' | 'risk_score'
  fill: string
  driver: keyof NonNullable<AthleteRecord['shap_drivers']>
}[] = [
  { letter: 'B', label: 'BRAND', key: 'brand_score', fill: styles.fillB, driver: 'brand' },
  { letter: 'P', label: 'PROOF', key: 'proof_score', fill: styles.fillP, driver: 'proof' },
  { letter: 'X', label: 'EXPOSURE', key: 'proximity_score', fill: styles.fillX, driver: 'proximity' },
  { letter: 'V', label: 'VELOCITY', key: 'velocity_score', fill: styles.fillV, driver: 'velocity' },
  { letter: 'R', label: 'RISK', key: 'risk_score', fill: styles.fillR, driver: 'risk' },
]

/**
 * Two-block breakdown of the Gravity Score:
 *   1. COMPONENT SCORES — what the five inputs (Brand/Proof/Exposure/Velocity/Risk)
 *      look like for this athlete, with their per-component movements.
 *   2. SHAP DRIVERS — the signed feature attribution that explains *why* the
 *      composite landed where it did. `top_factors_up` pulls the score up,
 *      `top_factors_down` pulls it down. Falls back to the legacy
 *      `shap_drivers` per-component narratives when factor lists are absent.
 */
export function BPXVRBreakdown({ athlete }: { athlete: AthleteRecord }) {
  const componentsUnavailable = ROWS.every((r) => athlete[r.key] == null)
  const factorsUp = athlete.top_factors_up ?? null
  const factorsDown = athlete.top_factors_down ?? null
  const driversUnavailable =
    !factorsUp?.length && !factorsDown?.length && ROWS.every((r) => !athlete.shap_drivers?.[r.driver])

  return (
    <div className={styles.stack}>
      <section className={styles.box} aria-label="Component scores">
        <h2 className={styles.title}>&gt;&gt; COMPONENT SCORES</h2>
        {componentsUnavailable && (
          <div className={styles.emptyState}>Component scores unavailable for this athlete.</div>
        )}
        {ROWS.map((r) => {
          const v = athlete[r.key]
          const pct = v == null ? 0 : Math.min(100, Math.max(0, v))
          const delta = athlete.component_deltas?.[r.driver as keyof NonNullable<AthleteRecord['component_deltas']>]
          return (
            <div key={r.letter} className={styles.row}>
              <span className={styles.letter}>{r.letter}</span>
              <span className={styles.componentLabel}>{r.label}</span>
              <div className={styles.track}>
                <div className={`${styles.fill} ${r.fill}`} style={{ width: `${pct}%` }} />
              </div>
              <span className={styles.score}>{formatScore(v)}</span>
              <span className={styles.deltaCell}>{formatDelta(delta ?? null)}</span>
            </div>
          )
        })}
      </section>

      <section className={styles.box} aria-label="SHAP drivers">
        <h2 className={styles.title}>&gt;&gt; SHAP DRIVERS</h2>
        {driversUnavailable ? (
          <div className={styles.emptyState}>Attribution unavailable for this athlete.</div>
        ) : (
          <>
            {factorsUp?.length || factorsDown?.length ? (
              <div className={styles.factorGrid}>
                <FactorList title="Pushing score up" tone="up" factors={factorsUp} />
                <FactorList title="Pulling score down" tone="down" factors={factorsDown} />
              </div>
            ) : (
              ROWS.map((r) => {
                const ctx = athlete.shap_drivers?.[r.driver]
                if (!ctx) return null
                return (
                  <div key={r.letter} className={styles.row}>
                    <span className={styles.letter}>{r.letter}</span>
                    <span className={styles.componentLabel}>{r.label}</span>
                    <span className={styles.driverCtx} title={ctx}>
                      {ctx}
                    </span>
                  </div>
                )
              })
            )}
          </>
        )}
      </section>
    </div>
  )
}

function FactorList({
  title,
  tone,
  factors,
}: {
  title: string
  tone: 'up' | 'down'
  factors: ShapFactor[] | null
}) {
  return (
    <div className={styles.factorCol}>
      <div className={`${styles.factorTitle} ${tone === 'up' ? styles.factorUpTitle : styles.factorDownTitle}`}>
        {title}
      </div>
      {factors?.length ? (
        <ul className={styles.factorList}>
          {factors.slice(0, 5).map((f, idx) => (
            <li key={`${f.feature}-${idx}`} className={styles.factorRow}>
              <span className={styles.factorLabel}>{f.display ?? formatFeatureName(f.feature)}</span>
              <span className={tone === 'up' ? styles.factorDeltaUp : styles.factorDeltaDown}>
                {formatShapDelta(f.delta)}
              </span>
            </li>
          ))}
        </ul>
      ) : (
        <div className={styles.factorEmpty}>—</div>
      )}
    </div>
  )
}

function formatFeatureName(feature: string): string {
  return feature.replace(/_/g, ' ').replace(/\blog\b/i, '(log)').toLowerCase()
}

function formatShapDelta(delta: number): string {
  const sign = delta > 0 ? '+' : delta < 0 ? '\u2212' : ''
  const abs = Math.abs(delta)
  if (abs >= 10) return `${sign}${abs.toFixed(1)}`
  return `${sign}${abs.toFixed(2)}`
}
