import { formatNilValue, formatNilRange, formatScore } from '../../lib/formatters'
import type { AthleteRecord } from '../../types/athlete'
import styles from './NilValuation.module.css'

export function NilValuation({ athlete }: { athlete: AthleteRecord }) {
  const pct = athlete.nil_valuation_percentile
  return (
    <div>
      <div className={styles.label}>NIL VALUATION</div>
      <div className={styles.value}>{formatNilValue(athlete.nil_valuation_consensus)}</div>
      <div className={styles.range}>
        {formatNilRange(athlete.nil_range_low, athlete.nil_range_high)}
      </div>
      {athlete.dollar_p10_usd != null && athlete.dollar_p90_usd != null && (
        <div className={styles.range}>
          Gravity money P10–P90: {formatNilRange(athlete.dollar_p10_usd, athlete.dollar_p90_usd)}
          {athlete.dollar_p50_usd != null && (
            <span> · P50 {formatNilValue(athlete.dollar_p50_usd)}</span>
          )}
        </div>
      )}
      {(athlete.company_gravity_score != null || athlete.brand_gravity_score != null) && (
        <div className={styles.meta}>
          {athlete.company_gravity_score != null && (
            <span>Company G: {formatScore(athlete.company_gravity_score)}</span>
          )}
          {athlete.company_gravity_score != null && athlete.brand_gravity_score != null && ' · '}
          {athlete.brand_gravity_score != null && (
            <span>Brand G: {formatScore(athlete.brand_gravity_score)}</span>
          )}
        </div>
      )}
      <div className={styles.meta}>
        {pct != null ? `${pct}TH PCT (POS / SPORT)` : 'PCT: \u2014'}
      </div>
      {athlete.dollar_confidence?.dollar_confidence_label != null && (
        <div className={styles.meta}>
          Model range confidence: {athlete.dollar_confidence.dollar_confidence_label}
          {athlete.dollar_confidence.dollar_comparable_verified_bucket != null
            ? ` · ${athlete.dollar_confidence.dollar_comparable_verified_bucket} comparable verified deals (bucket)`
            : ''}
        </div>
      )}
    </div>
  )
}
