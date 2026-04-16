import { useEffect } from 'react'
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
      <div className={styles.empty} style={{ fontFamily: 'var(--font-data)', color: 'var(--text-muted)' }}>
        {'\u2014'}
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
