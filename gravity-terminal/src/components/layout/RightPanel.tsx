import { useLocation } from 'react-router-dom'
import { exportBrandMatchShortlistCsv, exportBrandMatchShortlistPdf } from '../../lib/brandMatchExport'
import { useAthleteStore } from '../../stores/athleteStore'
import { useUiStore } from '../../stores/uiStore'
import { formatNilMillions, formatScore } from '../../lib/formatters'
import { AlternativesPanel } from '../panels/AlternativesPanel'
import { ConfidenceCard } from '../panels/ConfidenceCard'
import { DealActionPanel } from '../panels/DealActionPanel'
import { LiveFeedV2 } from '../panels/LiveFeedV2'
import { MarketSignals } from '../panels/MarketSignals'
import { NilValuation } from '../panels/NilValuation'
import { QuickActions } from '../panels/QuickActions'
import { ActionButton } from '../shared/ActionButton'
import styles from './RightPanel.module.css'

export function RightPanel() {
  const { pathname } = useLocation()
  const athlete = useAthleteStore((s) => s.activeAthlete)
  const brandSummary = useUiStore((s) => s.brandMatchSummary)
  const brandContext = useUiStore((s) => s.brandMatchResultContext)
  const shortlist = useUiStore((s) => s.brandMatchShortlist)
  const requestRefine = useUiStore((s) => s.requestBrandMatchRefine)
  const isNilIntelligenceRoute = pathname === '/'

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

  const dealActionBlock = (
    <div className={styles.section}>
      <DealActionPanel athleteId={athlete.athlete_id} />
    </div>
  )

  const confidenceBlock = (
    <div className={styles.section}>
      <ConfidenceCard athleteId={athlete.athlete_id} />
    </div>
  )

  const alternativesBlock = (
    <div className={styles.section}>
      <AlternativesPanel athleteId={athlete.athlete_id} />
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
    const shortlistP50 = shortlist.reduce((sum, row) => {
      const lo = row.deal_range_low
      const hi = row.deal_range_high
      if (typeof lo !== 'number' || typeof hi !== 'number') return sum
      return sum + (lo + hi) / 2
    }, 0)
    return (
      <aside className={styles.panel}>
        <div className={styles.scroll}>
          <div className={styles.section}>
            <div className={styles.title}>BRIEF SUMMARY</div>
            <p style={{ fontFamily: 'var(--font-prose)', fontSize: 10, color: 'var(--text-muted)' }}>
              {brandSummary ?? 'Configure brief and run FIND MATCHES.'}
            </p>
            <ActionButton variant="secondary" onClick={requestRefine}>
              REFINE BRIEF
            </ActionButton>
          </div>
          <div className={styles.section}>
            <div className={styles.title}>SHORTLIST</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 10, color: 'var(--text-secondary)' }}>
              {shortlist.length === 0 && (
                <div>ADD ATHLETES TO SHORTLIST USING THE ★ BUTTON</div>
              )}
              {shortlist.map((row) => (
                <div key={row.athlete_id} style={{ marginBottom: 6 }}>
                  <div>{row.name}</div>
                  <div style={{ color: 'var(--text-muted)' }}>
                    MATCH {formatScore(row.match_score)} · NIL {formatNilMillions(
                      typeof row.deal_range_low === 'number' && typeof row.deal_range_high === 'number'
                        ? (row.deal_range_low + row.deal_range_high) / 2
                        : null,
                    )}
                  </div>
                </div>
              ))}
              {shortlist.length > 0 && (
                <>
                  <div style={{ marginTop: 8 }}>Total budget est: {formatNilMillions(shortlistP50)}</div>
                  <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
                    <ActionButton variant="secondary" onClick={() => exportBrandMatchShortlistCsv(shortlist)}>
                      EXPORT CSV
                    </ActionButton>
                    <ActionButton variant="secondary" onClick={() => void exportBrandMatchShortlistPdf(shortlist)}>
                      EXPORT PDF
                    </ActionButton>
                  </div>
                </>
              )}
            </div>
          </div>
          <div className={styles.section}>
            <div className={styles.title}>MARKET CONTEXT</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 10, color: 'var(--text-secondary)' }}>
              <div>Median Match: {formatScore(brandContext?.median_match_score)}</div>
              <div>Median NIL P50: {formatNilMillions(brandContext?.median_nil_p50)}</div>
              <div>Median Reach: {brandContext?.median_social_reach != null ? Math.round(brandContext.median_social_reach).toLocaleString('en-US') : '—'}</div>
              <div>Median Engagement: {brandContext?.median_engagement_rate != null ? `${formatScore(brandContext.median_engagement_rate)}%` : '—'}</div>
              <div>Total matches: {brandContext?.total_matches ?? 0}</div>
            </div>
          </div>
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
        {isNilIntelligenceRoute && dealActionBlock}
        {isNilIntelligenceRoute && confidenceBlock}
        {isNilIntelligenceRoute && alternativesBlock}
        {signalsBlock}
        {feedBlock}
      </div>
      {quickBlock}
    </aside>
  )
}
