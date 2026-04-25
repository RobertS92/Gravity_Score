import { useLocation } from 'react-router-dom'
import { useAthleteStore } from '../../stores/athleteStore'
import { useUiStore } from '../../stores/uiStore'
import { useWatchlistStore } from '../../stores/watchlistStore'
import { formatNilMillions, formatScore } from '../../lib/formatters'
import { LiveFeedV2 } from '../panels/LiveFeedV2'
import { MarketSignals } from '../panels/MarketSignals'
import { NilValuation } from '../panels/NilValuation'
import { QuickActions } from '../panels/QuickActions'
import styles from './RightPanel.module.css'

export function RightPanel() {
  const { pathname } = useLocation()
  const athlete = useAthleteStore((s) => s.activeAthlete)
  const brandSummary = useUiStore((s) => s.brandMatchSummary)
  const watchlist = useWatchlistStore((s) => s.athletes)

  const fallbackFeedBlock = (
    <div className={styles.section}>
      <LiveFeedV2 />
    </div>
  )

  if (!athlete) {
    return (
      <aside className={styles.panel}>
        <div className={styles.scroll}>
          <div className={styles.section}>
            <div className={styles.title}>NIL VALUATION</div>
            <p style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-data)', fontSize: 10 }}>
              Pick an athlete from the watchlist to see their valuation.
            </p>
          </div>
          {fallbackFeedBlock}
        </div>
      </aside>
    )
  }

  const nilBlock = (
    <div className={styles.section}>
      <NilValuation athlete={athlete} />
    </div>
  )

  const signalsBlock = (
    <div className={styles.section}>
      <MarketSignals athlete={athlete} />
    </div>
  )

  const feedBlock = (
    <div className={styles.section}>
      <LiveFeedV2 />
    </div>
  )

  const quickBlock = (
    <div className={styles.footer}>
      <QuickActions />
    </div>
  )

  if (pathname.startsWith('/csc')) {
    return (
      <aside className={styles.panel}>
        <div className={styles.scroll}>
          {nilBlock}
          {signalsBlock}
        </div>
      </aside>
    )
  }

  if (pathname.startsWith('/brand-match')) {
    const medBrand =
      watchlist.length > 0
        ? watchlist.reduce((a, x) => a + (x.brand_score ?? 0), 0) / watchlist.length
        : null
    return (
      <aside className={styles.panel}>
        <div className={styles.scroll}>
          <div className={styles.section}>
            <div className={styles.title}>MATCH BRIEF</div>
            <p style={{ fontFamily: 'var(--font-prose)', fontSize: 10, color: 'var(--text-muted)' }}>
              {brandSummary ?? 'Configure brief and run FIND MATCHES.'}
            </p>
          </div>
          <div className={styles.section}>
            <div className={styles.title}>AGGREGATES</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 10, color: 'var(--text-secondary)' }}>
              <div>Median Brand: {formatScore(medBrand)}</div>
              <div>Watchlist n={watchlist.length}</div>
            </div>
          </div>
          {nilBlock}
        </div>
      </aside>
    )
  }

  if (pathname.startsWith('/monitoring')) {
    return (
      <aside className={styles.panel}>
        <div className={styles.scroll}>
          <div className={styles.section}>
            <div className={styles.title}>ALERT THRESHOLDS</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 10, color: 'var(--text-muted)' }}>
              <div>Score move: 3+ pts</div>
              <div>NIL signal: $50K+</div>
              <div>Risk: standard</div>
            </div>
          </div>
          {nilBlock}
          {signalsBlock}
        </div>
      </aside>
    )
  }

  if (pathname.startsWith('/market-scan')) {
    return (
      <aside className={styles.panel}>
        <div className={styles.scroll}>
          <div className={styles.section}>
            <div className={styles.title}>SCAN CONTEXT</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 10, color: 'var(--text-secondary)' }}>
              Active: {athlete.name}
              <br />
              NIL {formatNilMillions(athlete.nil_valuation_consensus)}
            </div>
          </div>
          {signalsBlock}
        </div>
      </aside>
    )
  }

  return (
    <aside className={styles.panel}>
      <div className={styles.scroll}>
        {nilBlock}
        {signalsBlock}
        {feedBlock}
      </div>
      {quickBlock}
    </aside>
  )
}
