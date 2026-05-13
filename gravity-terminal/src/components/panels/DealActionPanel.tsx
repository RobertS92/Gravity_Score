import { getDealAction } from '../../api/athletes'
import { useNilIntelligenceResource } from '../../hooks/useNilIntelligenceResource'
import { formatNilMillions } from '../../lib/formatters'
import { parseFiniteNumber } from '../../lib/numberParsing'
import type { DealActionResponse } from '../../types/nilIntelligence'
import styles from './NilDecisionPanel.module.css'

function recommendationClass(v: string) {
  if (v === 'OFFER_NOW') return styles.ok
  if (v === 'NEGOTIATE') return styles.warn
  if (v === 'WAIT') return styles.muted
  return styles.risk
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : null
}

function asFiniteNumber(value: unknown): number | null {
  return parseFiniteNumber(value)
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim().length > 0 ? value : null
}

export type SafeDealActionView = {
  recommendation: string
  recommendedLow: number | null
  recommendedHigh: number | null
  walkAway: number | null
  structureType: string
  termMonths: number | null
  rationale: string[]
}

export function toSafeDealActionView(data: unknown): SafeDealActionView {
  const root = asRecord(data)
  const structure = asRecord(root?.structure)
  const recommendation = asString(root?.recommendation) ?? 'PASS'
  const structureTypeRaw = asString(structure?.structure_type) ?? asString(structure?.type)
  const rationale = root?.rationale
  return {
    recommendation,
    recommendedLow: asFiniteNumber(root?.recommended_range_low_usd) ?? asFiniteNumber(root?.current_range_low),
    recommendedHigh: asFiniteNumber(root?.recommended_range_high_usd) ?? asFiniteNumber(root?.current_range_high),
    walkAway: asFiniteNumber(root?.walk_away_price_usd) ?? asFiniteNumber(root?.walk_away_price),
    structureType: structureTypeRaw ? structureTypeRaw.toUpperCase() : 'N/A',
    termMonths: asFiniteNumber(structure?.term_months),
    rationale: Array.isArray(rationale)
      ? rationale.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
      : typeof rationale === 'string' && rationale.trim().length > 0
        ? [rationale]
        : [],
  }
}

export function DealActionPanel({ athleteId }: { athleteId: string }) {
  const { data, loading, error } = useNilIntelligenceResource<DealActionResponse>(
    athleteId,
    getDealAction,
    'Failed to load deal action',
  )
  const safe = toSafeDealActionView(data)

  return (
    <div>
      <div className={styles.label}>DEAL ACTION</div>
      {loading && <div className={styles.muted}>Loading recommendation...</div>}
      {!loading && error && <div className={styles.error}>{error}</div>}
      {!loading && !error && data && (
        <>
          <div className={`${styles.headline} ${recommendationClass(safe.recommendation)}`}>
            {safe.recommendation.replaceAll('_', ' ')}
          </div>
          <div className={styles.row}>
            <span className={styles.k}>Recommended Range</span>
            <span className={styles.v}>
              {formatNilMillions(safe.recommendedLow)} -{' '}
              {formatNilMillions(safe.recommendedHigh)}
            </span>
          </div>
          <div className={styles.row}>
            <span className={styles.k}>Walk-Away</span>
            <span className={styles.v}>{formatNilMillions(safe.walkAway)}</span>
          </div>
          <div className={styles.row}>
            <span className={styles.k}>Structure</span>
            <span className={styles.v}>
              {safe.structureType}
              {safe.termMonths != null ? ` · ${safe.termMonths}M` : ''}
            </span>
          </div>
          {safe.rationale.length > 0 && (
            <ul className={styles.list}>
              {safe.rationale.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}
