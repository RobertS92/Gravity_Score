import { useLocation } from 'react-router-dom'
import { exportBrandMatchShortlistCsv, exportBrandMatchShortlistPdf } from '../../lib/brandMatchExport'
import { useAthleteStore } from '../../stores/athleteStore'
import { useUiStore } from '../../stores/uiStore'
import { formatNilValue, formatScore } from '../../lib/formatters'
import type { BrandMatchResult } from '../../types/reports'
import { AlternativesPanel } from '../panels/AlternativesPanel'
import { ConfidenceCard } from '../panels/ConfidenceCard'
import { DealActionPanel } from '../panels/DealActionPanel'
import { LiveFeedV2 } from '../panels/LiveFeedV2'
import { MarketSignals } from '../panels/MarketSignals'
import { NilValuation } from '../panels/NilValuation'
import { QuickActions } from '../panels/QuickActions'
import { ActionButton } from '../shared/ActionButton'
import styles from './RightPanel.module.css'

function safeShortlist(raw: unknown): BrandMatchResult[] {
  if (!Array.isArray(raw)) return []
  return raw.filter((row): row is BrandMatchResult => !!row && typeof row === 'object')
}

function rowNilP50(row: BrandMatchResult): number | null {
  const lo = row.deal_range_low
  const hi = row.deal_range_high
  if (typeof lo === 'number' && Number.isFinite(lo) && typeof hi === 'number' && Number.isFinite(hi)) {
    return (lo + hi) / 2
  }
  return null
}

export function getShortlistBudgetEstimate(raw: unknown): number {
  return safeShortlist(raw).reduce((sum, row) => sum + (rowNilP50(row) ?? 0), 0)
}

export function RightPanel() {
  const { pathname } = useLocation()
  const athlete = useAthleteStore((s) => s.activeAthlete)
  const brandSummary = useUiStore((s) => s.brandMatchSummary)
  const brandContext = useUiStore((s) => s.brandMatchResultContext)
  const shortlistRaw = useUiStore((s) => s.brandMatchShortlist) as unknown
  const shortlist = safeShortlist(shortlistRaw)
  const requestRefine = useUiStore((s) => s.requestBrandMatchRefine)
  const isNilIntelligenceRoute = pathname === '/'
  const athleteId = typeof athlete?.athlete_id === 'string' && athlete.athlete_id.length > 0 ? athlete.athlete_id : null

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
            <p style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-data)', fontSize: 12, lineHeight: 1.5 }}>
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
      {athleteId ? (
        <DealActionPanel athleteId={athleteId} />
      ) : (
        <div style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-data)', fontSize: 12 }}>
          Deal recommendation unavailable for this athlete.
        </div>
      )}
    </div>
  )

  const confidenceBlock = (
    <div className={styles.section}>
      {athleteId ? (
        <ConfidenceCard athleteId={athleteId} />
      ) : (
        <div style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-data)', fontSize: 12 }}>
          Confidence details unavailable for this athlete.
        </div>
      )}
    </div>
  )

  const alternativesBlock = (
    <div className={styles.section}>
      {athleteId ? (
        <AlternativesPanel athleteId={athleteId} />
      ) : (
        <div style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-data)', fontSize: 12 }}>
          Alternatives unavailable for this athlete.
        </div>
      )}
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
    const shortlistP50 = getShortlistBudgetEstimate(shortlistRaw)
    return (
      <aside className={styles.panel}>
        <div className={styles.scroll}>
          <div className={styles.section}>
            <div className={styles.title}>BRIEF SUMMARY</div>
            <p style={{ fontFamily: 'var(--font-prose)', fontSize: 12, lineHeight: 1.5, color: 'var(--text-muted)' }}>
              {brandSummary ?? 'Configure brief and run FIND MATCHES.'}
            </p>
            <ActionButton variant="secondary" onClick={() => requestRefine?.()}>
              REFINE BRIEF
            </ActionButton>
          </div>
          <div className={styles.section}>
            <div className={styles.title}>SHORTLIST</div>
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 12, color: 'var(--text-secondary)' }}>
              {shortlist.length === 0 && (
                <div>ADD ATHLETES TO SHORTLIST USING THE ★ BUTTON</div>
              )}
              {shortlist.map((row, idx) => (
                <div key={row.athlete_id ?? `${row.name ?? 'shortlist'}-${idx}`} style={{ marginBottom: 6 }}>
                  <div>{row.name}</div>
                  <div style={{ color: 'var(--text-muted)' }}>
                    MATCH {formatScore(row.match_score)} · NIL {formatNilValue(rowNilP50(row))}
                  </div>
                </div>
              ))}
              {shortlist.length > 0 && (
                <>
                  <div style={{ marginTop: 8 }}>Total budget est: {formatNilValue(shortlistP50)}</div>
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
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 12, color: 'var(--text-secondary)' }}>
              <div>Median Match: {formatScore(brandContext?.median_match_score)}</div>
              <div>Median NIL P50: {formatNilValue(brandContext?.median_nil_p50)}</div>
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
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 12, color: 'var(--text-muted)' }}>
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
            <div style={{ fontFamily: 'var(--font-data)', fontSize: 12, color: 'var(--text-secondary)' }}>
              Active: {athlete.name}
              <br />
              NIL {formatNilValue(athlete.nil_valuation_consensus)}
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
