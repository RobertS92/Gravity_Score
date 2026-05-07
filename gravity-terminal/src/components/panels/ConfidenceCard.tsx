import { getConfidence } from '../../api/athletes'
import { useNilIntelligenceResource } from '../../hooks/useNilIntelligenceResource'
import type { ConfidenceResponse } from '../../types/nilIntelligence'
import styles from './NilDecisionPanel.module.css'

function labelClass(label: ConfidenceResponse['overall_label']) {
  if (label === 'HIGH') return styles.ok
  if (label === 'MEDIUM') return styles.warn
  return styles.risk
}

export function ConfidenceCard({ athleteId }: { athleteId: string }) {
  const { data, loading, error } = useNilIntelligenceResource<ConfidenceResponse>(
    athleteId,
    getConfidence,
    'Failed to load confidence',
  )

  return (
    <div>
      <div className={styles.label}>CONFIDENCE CARD</div>
      {loading && <div className={styles.muted}>Loading confidence...</div>}
      {!loading && error && <div className={styles.error}>{error}</div>}
      {!loading && !error && data && (
        <>
          <div className={`${styles.headline} ${labelClass(data.overall_label)}`}>
            {(data.overall_score * 100).toFixed(0)}% · {data.overall_label}
          </div>
          {data.factors.slice(0, 3).map((f) => (
            <div className={styles.row} key={f.key}>
              <span className={styles.k}>{f.label}</span>
              <span className={styles.v}>{(f.score * 100).toFixed(0)}%</span>
            </div>
          ))}
          {data.caveats.length > 0 && (
            <ul className={styles.list}>
              {data.caveats.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}
