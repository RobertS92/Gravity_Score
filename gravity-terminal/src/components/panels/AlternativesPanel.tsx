import { getAlternatives } from '../../api/athletes'
import { useNilIntelligenceResource } from '../../hooks/useNilIntelligenceResource'
import { formatNilValue } from '../../lib/formatters'
import { parseFiniteNumber } from '../../lib/numberParsing'
import type { AlternativesResponse } from '../../types/nilIntelligence'
import styles from './NilDecisionPanel.module.css'

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : null
}

function asFiniteNumber(value: unknown): number | null {
  return parseFiniteNumber(value)
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim().length > 0 ? value : null
}

type SafeAlternative = {
  athleteId: string
  name: string
  school: string | null
  nilConsensus: number | null
  fitScore: number | null
  whyBetter: string | null
}

export function toSafeAlternatives(data: unknown): SafeAlternative[] {
  const root = asRecord(data)
  const rows = Array.isArray(root?.alternatives)
    ? root.alternatives
    : Array.isArray(root?.candidates)
      ? root.candidates
      : []
  return rows
    .map((row, idx) => {
      const item = asRecord(row)
      const athleteId = asString(item?.athlete_id) ?? `alt-${idx}`
      return {
        athleteId,
        name: asString(item?.name) ?? 'Unknown',
        school: asString(item?.school),
        nilConsensus: asFiniteNumber(item?.nil_valuation_consensus) ?? asFiniteNumber(item?.nil_estimate),
        fitScore: asFiniteNumber(item?.fit_score),
        whyBetter: asString(item?.why_better),
      }
    })
}

export function AlternativesPanel({ athleteId }: { athleteId: string }) {
  const { data, loading, error } = useNilIntelligenceResource<AlternativesResponse>(
    athleteId,
    getAlternatives,
    'Failed to load alternatives',
  )
  const alternatives = toSafeAlternatives(data)

  return (
    <div>
      <div className={styles.label}>ALTERNATIVES</div>
      {loading && <div className={styles.muted}>Loading alternatives...</div>}
      {!loading && error && <div className={styles.error}>{error}</div>}
      {!loading && !error && data && alternatives.length === 0 && (
        <div className={styles.muted}>No alternatives available for this cohort.</div>
      )}
      {!loading && !error && data && alternatives.length > 0 && (
        <>
          {alternatives.map((alt) => (
            <div key={alt.athleteId} className={styles.alt}>
              <div className={styles.altName}>
                {alt.name} · {alt.school ?? '—'}
              </div>
              <div className={styles.row}>
                <span className={styles.k}>NIL Est.</span>
                <span className={styles.v}>{formatNilValue(alt.nilConsensus)}</span>
              </div>
              <div className={styles.row}>
                <span className={styles.k}>Fit Score</span>
                <span className={styles.v}>{alt.fitScore ?? '—'}</span>
              </div>
              <div className={styles.muted}>{alt.whyBetter ?? '—'}</div>
            </div>
          ))}
        </>
      )}
    </div>
  )
}
