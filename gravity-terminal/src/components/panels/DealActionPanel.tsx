import { getDealAction } from '../../api/athletes'
import { useNilIntelligenceResource } from '../../hooks/useNilIntelligenceResource'
import { formatNilMillions } from '../../lib/formatters'
import type { DealActionResponse } from '../../types/nilIntelligence'
import styles from './NilDecisionPanel.module.css'

function recommendationClass(v: DealActionResponse['recommendation']) {
  if (v === 'OFFER_NOW') return styles.ok
  if (v === 'NEGOTIATE') return styles.warn
  if (v === 'WAIT') return styles.muted
  return styles.risk
}

export function DealActionPanel({ athleteId }: { athleteId: string }) {
  const { data, loading, error } = useNilIntelligenceResource<DealActionResponse>(
    athleteId,
    getDealAction,
    'Failed to load deal action',
  )

  return (
    <div>
      <div className={styles.label}>DEAL ACTION</div>
      {loading && <div className={styles.muted}>Loading recommendation...</div>}
      {!loading && error && <div className={styles.error}>{error}</div>}
      {!loading && !error && data && (
        <>
          <div className={`${styles.headline} ${recommendationClass(data.recommendation)}`}>
            {data.recommendation.replace('_', ' ')}
          </div>
          <div className={styles.row}>
            <span className={styles.k}>Recommended Range</span>
            <span className={styles.v}>
              {formatNilMillions(data.recommended_range_low_usd)} -{' '}
              {formatNilMillions(data.recommended_range_high_usd)}
            </span>
          </div>
          <div className={styles.row}>
            <span className={styles.k}>Walk-Away</span>
            <span className={styles.v}>{formatNilMillions(data.walk_away_price_usd)}</span>
          </div>
          <div className={styles.row}>
            <span className={styles.k}>Structure</span>
            <span className={styles.v}>
              {data.structure.structure_type.toUpperCase()} · {data.structure.term_months}M
            </span>
          </div>
          <ul className={styles.list}>
            {data.rationale.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
