import { useEffect } from 'react'
import { Link } from 'react-router-dom'
import { useAthleteStore } from '../../stores/athleteStore'
import { useUiStore } from '../../stores/uiStore'
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
  const isLoading = useAthleteStore((s) => s.isLoading)
  const error = useAthleteStore((s) => s.error)
  const consume = useAthleteStore((s) => s.consumeScoreAnimation)
  const athleteCorpusEmpty = useUiStore((s) => s.athleteCorpusEmpty)

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
        <div className={isLoading ? styles.loadingMark : styles.emptyMark} aria-hidden>
          {isLoading ? 'G' : '—'}
        </div>
        <div className={styles.emptyTitle}>
          {isLoading
            ? 'LOADING ATHLETE INTELLIGENCE'
            : athleteCorpusEmpty
              ? 'ATHLETES UNAVAILABLE'
              : 'NO ATHLETE SELECTED'}
        </div>
        <div className={styles.emptyCopy}>
          {isLoading ? (
            <>Loading the latest athlete profile and valuation signals…</>
          ) : athleteCorpusEmpty || error ? (
            <>
              We couldn&apos;t load an athlete profile right now.{' '}
              <Link to="/market-scan" className={styles.emptyLink}>
                Browse athletes
              </Link>{' '}
              or refresh to try again.
            </>
          ) : (
            <>
              Pick an athlete from{' '}
              <Link to="/market-scan" className={styles.emptyLink}>
                Market Scan
              </Link>{' '}
              or search with the command bar to load their NIL intelligence profile.
            </>
          )}
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
