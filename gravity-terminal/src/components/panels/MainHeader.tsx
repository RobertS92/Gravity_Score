import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { formatDelta } from '../../lib/formatters'
import { formatUpdatedAgo } from '../../lib/time'
import { downloadAthleteScoreCardPdf } from '../../lib/pdfExport'
import type { AthleteRecord } from '../../types/athlete'
import { ActionButton } from '../shared/ActionButton'
import { ScoreDisplay } from '../shared/ScoreDisplay'
import { TeamFavoriteStar } from '../shared/TeamFavoriteStar'
import styles from './MainHeader.module.css'

function dotJoin(parts: (string | null | undefined)[]) {
  return parts.filter(Boolean).join(' · ')
}

export function MainHeader({
  athlete,
  animateScore,
}: {
  athlete: AthleteRecord
  animateScore: boolean
}) {
  const navigate = useNavigate()
  const [pdfLoading, setPdfLoading] = useState(false)
  const [explainerOpen, setExplainerOpen] = useState(false)
  const explainerRef = useRef<HTMLDivElement>(null)

  // Close the explainer popover on outside click or Escape so it doesn't
  // trap focus when the user moves on.
  useEffect(() => {
    if (!explainerOpen) return
    const onClick = (e: MouseEvent) => {
      if (!explainerRef.current?.contains(e.target as Node)) {
        setExplainerOpen(false)
      }
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setExplainerOpen(false)
    }
    document.addEventListener('mousedown', onClick)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [explainerOpen])

  const handlePdf = async () => {
    setPdfLoading(true)
    try { await downloadAthleteScoreCardPdf(athlete) } finally { setPdfLoading(false) }
  }
  const meta = dotJoin([
    athlete.position,
    athlete.school,
    athlete.class_year,
    athlete.jersey_number ? `#${athlete.jersey_number}` : null,
    athlete.height && athlete.weight ? `${athlete.height} ${athlete.weight}` : athlete.height ?? athlete.weight,
  ])
  const d = athlete.gravity_delta_30d
  const deltaCls = d == null ? styles.delta : d >= 0 ? styles.deltaPos : styles.deltaNeg
  const upd = formatUpdatedAgo(athlete.updated_at)

  return (
    <header className={styles.wrap}>
      <div className={styles.left}>
        <h1 className={styles.name}>{athlete.name}</h1>
        <div className={styles.meta}>
          {meta || '\u2014'}
          {athlete.team_id && athlete.school && (
            <span style={{ marginLeft: 8, display: 'inline-flex', alignItems: 'center', gap: 4 }}>
              <TeamFavoriteStar teamId={athlete.team_id} teamName={athlete.school} size="md" />
            </span>
          )}
        </div>
      </div>
      <div className={styles.right}>
        <div className={styles.scoreBlock} ref={explainerRef}>
          <span className={styles.scoreLabel}>
            GRAVITY SCORE
            <button
              type="button"
              className={styles.explainerToggle}
              aria-label="How is this calculated?"
              aria-expanded={explainerOpen}
              onClick={() => setExplainerOpen((v) => !v)}
            >
              ?
            </button>
          </span>
          <div className={styles.scoreRow}>
            <ScoreDisplay
              key={athlete.athlete_id}
              value={athlete.gravity_score}
              animate={animateScore}
              className={styles.scoreVal}
            />
            <span className={`${styles.delta} ${deltaCls}`}>{formatDelta(d)}</span>
          </div>
          <span className={upd.stale ? styles.updatedStale : styles.updated}>{upd.text}</span>
          {explainerOpen && (
            <div className={styles.explainerPopover} role="dialog" aria-label="Gravity Score formula">
              <div className={styles.explainerTitle}>HOW THIS IS CALCULATED</div>
              <p className={styles.explainerBody}>
                Gravity Score is a 0–100 composite of five inputs that the
                GravityNet model weights for each athlete cohort:
              </p>
              <ul className={styles.explainerList}>
                <li><strong>Brand</strong> — followers · engagement · IG · TikTok · X</li>
                <li><strong>Proof</strong> — verified NIL deals · publicly reported deal value</li>
                <li><strong>Exposure</strong> — news · search · Wikipedia · proximity to spotlight</li>
                <li><strong>Velocity</strong> — 30-day deltas across the inputs above</li>
                <li><strong>Risk</strong> — roster status · model confidence · data quality</li>
              </ul>
              <p className={styles.explainerFooter}>
                Weights vary by sport &amp; position group. Top SHAP drivers
                appear below in the breakdown. Fallback model: heuristic
                weights (see Settings → Weighting).
              </p>
            </div>
          )}
        </div>
        <div className={styles.scoreBlock}>
          <span className={styles.scoreLabel}>TIER</span>
          <span className={styles.tier}>{athlete.gravity_tier ?? '\u2014'}</span>
          <span className={styles.scoreLabel}>PCT</span>
          <span className={styles.pct}>
            {athlete.gravity_percentile != null ? `${athlete.gravity_percentile}TH` : '\u2014'}
          </span>
          {athlete.company_gravity_score != null && (
            <>
              <span className={styles.scoreLabel}>PROGRAM G</span>
              <span className={styles.programG}>
                {athlete.company_gravity_score.toFixed(1)}
              </span>
            </>
          )}
        </div>
        <div className={styles.actions}>
          <ActionButton variant="secondary" onClick={() => navigate('/csc')}>
            CSC REPORT
          </ActionButton>
          <ActionButton variant="primary" onClick={() => void handlePdf()} disabled={pdfLoading}>
            {pdfLoading ? 'GENERATING…' : 'GENERATE PDF'}
          </ActionButton>
        </div>
      </div>
    </header>
  )
}
