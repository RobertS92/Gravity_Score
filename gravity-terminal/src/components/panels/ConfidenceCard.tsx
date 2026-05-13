import { getConfidence } from '../../api/athletes'
import { useNilIntelligenceResource } from '../../hooks/useNilIntelligenceResource'
import type { ConfidenceResponse } from '../../types/nilIntelligence'
import styles from './NilDecisionPanel.module.css'

function labelClass(label: string) {
  if (label === 'HIGH') return styles.ok
  if (label === 'MEDIUM') return styles.warn
  return styles.risk
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : null
}

function asFiniteNumber(value: unknown): number | null {
  if (typeof value === 'number' && Number.isFinite(value)) return value
  if (typeof value === 'string') {
    const parsed = Number(value.trim())
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

function asString(value: unknown): string | null {
  return typeof value === 'string' && value.trim().length > 0 ? value : null
}

type SafeConfidenceFactor = {
  key: string
  label: string
  score: number | null
}

export type SafeConfidenceView = {
  overallLabel: string
  overallScore: number | null
  factors: SafeConfidenceFactor[]
  caveats: string[]
}

export function toSafeConfidenceView(data: unknown): SafeConfidenceView {
  const root = asRecord(data)
  const factorRows = Array.isArray(root?.factors) ? root.factors : []
  return {
    overallLabel: asString(root?.overall_label) ?? 'LOW',
    overallScore: asFiniteNumber(root?.overall_score),
    factors: factorRows
      .map((entry, idx) => {
        const item = asRecord(entry)
        return {
          key: asString(item?.key) ?? `factor-${idx}`,
          label: asString(item?.label) ?? 'Factor',
          score: asFiniteNumber(item?.score),
        }
      })
      .slice(0, 3),
    caveats: Array.isArray(root?.caveats)
      ? root.caveats.filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
      : [],
  }
}

export function ConfidenceCard({ athleteId }: { athleteId: string }) {
  const { data, loading, error } = useNilIntelligenceResource<ConfidenceResponse>(
    athleteId,
    getConfidence,
    'Failed to load confidence',
  )
  const safe = toSafeConfidenceView(data)

  return (
    <div>
      <div className={styles.label}>CONFIDENCE CARD</div>
      {loading && <div className={styles.muted}>Loading confidence...</div>}
      {!loading && error && <div className={styles.error}>{error}</div>}
      {!loading && !error && data && (
        <>
          <div className={`${styles.headline} ${labelClass(safe.overallLabel)}`}>
            {safe.overallScore != null ? `${(safe.overallScore * 100).toFixed(0)}%` : '—'} · {safe.overallLabel}
          </div>
          {safe.factors.map((f) => (
            <div className={styles.row} key={f.key}>
              <span className={styles.k}>{f.label}</span>
              <span className={styles.v}>{f.score != null ? `${(f.score * 100).toFixed(0)}%` : '—'}</span>
            </div>
          ))}
          {safe.caveats.length > 0 && (
            <ul className={styles.list}>
              {safe.caveats.map((c) => (
                <li key={c}>{c}</li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  )
}
