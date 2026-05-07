import { getAlternatives } from '../../api/athletes'
import { useNilIntelligenceResource } from '../../hooks/useNilIntelligenceResource'
import { formatNilMillions } from '../../lib/formatters'
import type { AlternativesResponse } from '../../types/nilIntelligence'
import styles from './NilDecisionPanel.module.css'

export function AlternativesPanel({ athleteId }: { athleteId: string }) {
  const { data, loading, error } = useNilIntelligenceResource<AlternativesResponse>(
    athleteId,
    getAlternatives,
    'Failed to load alternatives',
  )

  return (
    <div>
      <div className={styles.label}>ALTERNATIVES</div>
      {loading && <div className={styles.muted}>Loading alternatives...</div>}
      {!loading && error && <div className={styles.error}>{error}</div>}
      {!loading && !error && data && data.alternatives.length === 0 && (
        <div className={styles.muted}>No alternatives available for this cohort.</div>
      )}
      {!loading && !error && data && data.alternatives.length > 0 && (
        <>
          {data.alternatives.map((alt) => (
            <div key={alt.athlete_id} className={styles.alt}>
              <div className={styles.altName}>
                {alt.name} · {alt.school ?? '—'}
              </div>
              <div className={styles.row}>
                <span className={styles.k}>NIL Est.</span>
                <span className={styles.v}>{formatNilMillions(alt.nil_valuation_consensus)}</span>
              </div>
              <div className={styles.row}>
                <span className={styles.k}>Fit Score</span>
                <span className={styles.v}>{alt.fit_score}</span>
              </div>
              <div className={styles.muted}>{alt.why_better}</div>
            </div>
          ))}
        </>
      )}
    </div>
  )
}
