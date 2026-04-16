import { useEffect, useRef, useState } from 'react'
import { formatDelta, formatScore } from '../../lib/formatters'
import type { AthleteRecord, ComponentDeltas } from '../../types/athlete'
import styles from './MetricsRow.module.css'

type Dim = 'brand' | 'proof' | 'proximity' | 'velocity' | 'risk' | 'program' | 'deal_brands'

function riskColor(risk: number | null | undefined) {
  if (risk == null) return styles.cMuted
  return risk <= 25 ? styles.cRiskLo : styles.cRiskHi
}

function dimColor(dim: Dim, athlete: AthleteRecord) {
  if (dim === 'brand') return styles.cBlue
  if (dim === 'velocity') return styles.cGreen
  if (dim === 'proximity') return styles.cPurple
  if (dim === 'risk') return riskColor(athlete.risk_score)
  if (dim === 'program') return styles.cAmber
  if (dim === 'deal_brands') return styles.cTeal
  return styles.cMuted
}

function deltaFor(d: ComponentDeltas | null | undefined, key: keyof ComponentDeltas) {
  return d?.[key] ?? null
}

type ContextCell = {
  dim: Dim
  label: string
  val: number | null | undefined
  dk?: keyof ComponentDeltas
  tooltip?: string
}

export function MetricsRow({ athlete }: { athlete: AthleteRecord }) {
  const prev = useRef<string>('')
  const [flash, setFlash] = useState(false)
  const sig = [
    athlete.brand_score,
    athlete.proof_score,
    athlete.proximity_score,
    athlete.velocity_score,
    athlete.risk_score,
    athlete.company_gravity_score,
    athlete.brand_gravity_score,
  ].join('|')

  useEffect(() => {
    if (!prev.current) {
      prev.current = sig
      return
    }
    if (prev.current !== sig) {
      setFlash(true)
      window.setTimeout(() => setFlash(false), 650)
    }
    prev.current = sig
  }, [sig])

  const coreCells: ContextCell[] = [
    { dim: 'brand', label: 'BRAND', val: athlete.brand_score, dk: 'brand' },
    { dim: 'proof', label: 'PROOF', val: athlete.proof_score, dk: 'proof' },
    { dim: 'proximity', label: 'PROXIMITY', val: athlete.proximity_score, dk: 'proximity' },
    { dim: 'velocity', label: 'VELOCITY', val: athlete.velocity_score, dk: 'velocity' },
    { dim: 'risk', label: 'RISK', val: athlete.risk_score, dk: 'risk' },
  ]

  const contextCells: ContextCell[] = [
    {
      dim: 'program',
      label: 'PROGRAM G',
      val: athlete.company_gravity_score,
      tooltip: "Program's sport-specific Gravity score",
    },
    {
      dim: 'deal_brands',
      label: 'DEAL BRANDS',
      val: athlete.brand_gravity_score,
      tooltip: 'Mean Gravity of active NIL deal brands',
    },
  ]

  const allCells = [...coreCells, ...contextCells]

  return (
    <div className={styles.grid}>
      {allCells.map((c) => (
        <div key={c.label} className={styles.cell} title={c.tooltip}>
          <div className={styles.label}>{c.label}</div>
          <div className={`${styles.val} ${dimColor(c.dim, athlete)} ${flash ? styles.flash : ''}`}>
            {formatScore(c.val)}
          </div>
          {c.dk && (
            <div className={styles.delta} style={{ color: 'var(--text-muted)' }}>
              {formatDelta(deltaFor(athlete.component_deltas, c.dk))}
            </div>
          )}
          {!c.dk && <div className={styles.delta} />}
        </div>
      ))}
    </div>
  )
}
