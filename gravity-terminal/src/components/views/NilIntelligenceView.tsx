import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAthleteStore } from '../../stores/athleteStore'
import { BPXVRBreakdown } from '../panels/BPXVRBreakdown'
import { ComparablesTable } from '../panels/ComparablesTable'
import { MainHeader } from '../panels/MainHeader'
import { MetricsRow } from '../panels/MetricsRow'
import { ScoreHistorySparkline } from '../panels/ScoreHistorySparkline'
import styles from './NilIntelligenceView.module.css'

export function NilIntelligenceView() {
  const athlete = useAthleteStore((s) => s.activeAthlete)
  const comparables = useAthleteStore((s) => s.comparables)
  const scoreHistory = useAthleteStore((s) => s.scoreHistory)
  const pending = useAthleteStore((s) => s.scoreAnimationPending)
  const consume = useAthleteStore((s) => s.consumeScoreAnimation)

  useEffect(() => {
    if (!pending) return
    const t = window.setTimeout(() => consume(), 900)
    return () => clearTimeout(t)
  }, [pending, consume])

  if (!athlete) {
    return (
      <div
        className={styles.empty}
        style={{
          fontFamily: 'var(--font-data)',
          color: 'var(--text-muted)',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          gap: 12,
          padding: '48px 24px',
          textAlign: 'center',
        }}
      >
        <div style={{ fontSize: 14, letterSpacing: '0.08em', textTransform: 'uppercase' }}>
          NO ATHLETE SELECTED
        </div>
        <div style={{ fontSize: 12, maxWidth: 420, lineHeight: 1.5 }}>
          Pick an athlete from{' '}
          <Link to="/market-scan" style={{ color: 'var(--accent-green)' }}>
            Market Scan
          </Link>{' '}
          or search with the command bar to load their NIL intelligence profile.
        </div>
      </div>
    )
  }

  return (
    <div className={styles.root}>
      <MainHeader athlete={athlete} animateScore={pending} />
      <div className={styles.sparkLabel}>SCORE HISTORY (30D)</div>
      <ScoreHistorySparkline data={scoreHistory} />
      <MetricsRow athlete={athlete} />
      <BPXVRBreakdown athlete={athlete} />
      <ComparablesTable athlete={athlete} comparables={comparables} />
    </div>
  )
}
