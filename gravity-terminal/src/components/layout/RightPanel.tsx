import { useEffect, useMemo, useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import {
  fetchCapScenarios,
  fetchCapUtilization,
  fetchCapWorkflowQueue,
  type CapScenario,
  type UtilizationResponse,
} from '../../api/cap'
import { exportBrandMatchShortlistCsv, exportBrandMatchShortlistPdf } from '../../lib/brandMatchExport'
import { primaryCapSportFromPrefs } from '../../lib/capSport'
import { formatNilValue, formatScore } from '../../lib/formatters'
import { centsToDollars } from '../../lib/orgAccess'
import { useAthleteStore } from '../../stores/athleteStore'
import { useAuthStore } from '../../stores/authStore'
import { usePreferencesStore } from '../../stores/preferencesStore'
import { useUiStore } from '../../stores/uiStore'
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
    // Market Signals are now embedded inside each Key Value Driver card
    // (see CscReportsView KeyValueDriversSection). The right rail on /csc
    // intentionally stays minimal so the report owns the screen.
    return (
      <aside className={styles.panel}>
        <div className={styles.scroll} />
        {quickBlock}
      </aside>
    )
  }

  if (pathname.startsWith('/cap')) {
    // Cap Management decision layer surface. The right rail here shows
    // org-wide cap state (utilization, headroom), in-flight scenarios, and
    // pending approvals — the operator's "where am I right now" panel.
    //
    // On the dedicated /cap/deal-desk view we additionally surface the
    // athlete-scoped decision blocks (DealAction / Confidence / Alternatives)
    // that previously lived on the NIL Intelligence home.
    const isDealDesk = pathname.startsWith('/cap/deal-desk')
    return (
      <aside className={styles.panel}>
        <div className={styles.scroll}>
          <CapUtilizationBlock />
          {isDealDesk && athleteId ? (
            <>
              {dealActionBlock}
              {confidenceBlock}
              {alternativesBlock}
            </>
          ) : (
            <>
              <CapScenariosBlock />
              <CapApprovalsBlock />
            </>
          )}
        </div>
        {quickBlock}
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
              <div>Score move: 3+ pts (~30d)</div>
              <div>NIL signal: P50 $250K+</div>
              <div>Risk: composite 65+</div>
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

  // NIL Intelligence home (`/`) intentionally focuses on valuation +
  // signals only. The decision-oriented blocks (DealAction / Confidence /
  // Alternatives) live on `/cap/deal-desk` so the Intelligence vs Cap
  // separation is enforced in the layout itself.
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

function CapUnlinkedNotice({ surface }: { surface: string }) {
  return (
    <div style={{ fontFamily: 'var(--font-data)', fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.55 }}>
      <div style={{ color: 'var(--accent-amber)', marginBottom: 6 }}>No organization linked</div>
      <div style={{ color: 'var(--text-muted)', fontSize: 11 }}>
        {surface} requires CapIQ membership — not the Settings profile label. Link a school/collective org in{' '}
        <Link to="/settings" style={{ color: 'var(--accent-cyan)' }}>
          Settings
        </Link>{' '}
        (see CapIQ access) or complete school onboarding.
      </div>
    </div>
  )
}

function CapUtilizationBlock() {
  const organizationId = useAuthStore((s) => s.organizationId)
  const activeSports = usePreferencesStore((s) => s.activeSports)
  const sport = useMemo(() => primaryCapSportFromPrefs(activeSports), [activeSports])
  const fy = useMemo(() => new Date().getFullYear(), [])
  const [util, setUtil] = useState<UtilizationResponse | null>(null)
  const [loading, setLoading] = useState(false)
  const [err, setErr] = useState<string | null>(null)

  useEffect(() => {
    if (!organizationId) {
      setUtil(null)
      setErr(null)
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    setErr(null)
    void fetchCapUtilization(organizationId, sport, fy)
      .then((u) => {
        if (!cancelled) setUtil(u)
      })
      .catch((e) => {
        if (!cancelled) {
          setUtil(null)
          setErr(e instanceof Error ? e.message : 'Failed to load utilization')
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [organizationId, sport, fy])

  const allocation = centsToDollars(util?.total_allocation_cents)
  const committed = centsToDollars(util?.committed_cents)
  const headroom =
    util?.remaining_cents != null
      ? centsToDollars(util.remaining_cents)
      : allocation != null && committed != null
        ? allocation - committed
        : null
  const pct = util?.utilization_pct
  const barWidth = pct != null && Number.isFinite(pct) ? `${Math.max(0, Math.min(pct, 100))}%` : '0%'

  return (
    <div className={styles.section}>
      <div className={styles.title}>CAP UTILIZATION</div>
      {!organizationId ? (
        <CapUnlinkedNotice surface="Live budget figures" />
      ) : loading && !util ? (
        <div style={{ fontFamily: 'var(--font-data)', fontSize: 12, color: 'var(--text-muted)' }}>
          Loading {sport} {fy} utilization…
        </div>
      ) : err ? (
        <div style={{ fontFamily: 'var(--font-data)', fontSize: 12, color: 'var(--accent-amber)' }}>{err}</div>
      ) : (
        <div style={{ fontFamily: 'var(--font-data)', fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 6 }}>
            Live · {sport} · FY {fy}
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>Total budget</span>
            <span>{formatNilValue(allocation)}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>Committed</span>
            <span style={{ color: 'var(--accent-amber)' }}>{formatNilValue(committed)}</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span>Headroom</span>
            <span style={{ color: 'var(--accent-green)' }}>{formatNilValue(headroom)}</span>
          </div>
          <div style={{ marginTop: 6, height: 6, background: 'var(--bg-primary)', position: 'relative' }}>
            <div
              style={{
                position: 'absolute',
                top: 0,
                left: 0,
                bottom: 0,
                width: barWidth,
                background: 'var(--accent-amber)',
                opacity: 0.85,
              }}
              aria-label={pct != null ? `Cap utilization ${pct.toFixed(0)}%` : 'Cap utilization unavailable'}
            />
          </div>
          <div style={{ marginTop: 4, fontSize: 10, color: 'var(--text-muted)' }}>
            {pct != null ? `${pct.toFixed(0)}% utilized` : 'Utilization unavailable'} ·{' '}
            <Link to="/cap" style={{ color: 'var(--accent-cyan)' }}>
              CapIQ dashboard
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}

function CapScenariosBlock() {
  const organizationId = useAuthStore((s) => s.organizationId)
  const activeSports = usePreferencesStore((s) => s.activeSports)
  const sport = useMemo(() => primaryCapSportFromPrefs(activeSports), [activeSports])
  const [scenarios, setScenarios] = useState<CapScenario[]>([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!organizationId) {
      setScenarios([])
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    void fetchCapScenarios(organizationId, sport)
      .then((r) => {
        if (!cancelled) setScenarios(r.scenarios ?? [])
      })
      .catch(() => {
        if (!cancelled) setScenarios([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [organizationId, sport])

  return (
    <div className={styles.section}>
      <div className={styles.title}>ACTIVE SCENARIOS</div>
      {!organizationId ? (
        <CapUnlinkedNotice surface="Scenarios" />
      ) : loading && scenarios.length === 0 ? (
        <div style={{ fontFamily: 'var(--font-data)', fontSize: 12, color: 'var(--text-muted)' }}>Loading…</div>
      ) : scenarios.length === 0 ? (
        <div style={{ fontFamily: 'var(--font-data)', fontSize: 12, color: 'var(--text-muted)', lineHeight: 1.5 }}>
          No scenarios yet.{' '}
          <Link to="/cap/scenarios" style={{ color: 'var(--accent-cyan)' }}>
            Open scenarios
          </Link>
        </div>
      ) : (
        <div style={{ fontFamily: 'var(--font-data)', fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.5 }}>
          {scenarios.slice(0, 5).map((s) => (
            <div key={s.id}>
              · {s.name}
              {s.status ? ` — ${s.status}` : ''}
              {s.total_committed != null ? ` · ${formatNilValue(centsToDollars(s.total_committed))}` : ''}
            </div>
          ))}
          <div style={{ marginTop: 6, fontSize: 10, color: 'var(--text-muted)' }}>
            <Link to="/cap/scenarios" style={{ color: 'var(--accent-cyan)' }}>
              View all
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}

function CapApprovalsBlock() {
  const organizationId = useAuthStore((s) => s.organizationId)
  const activeSports = usePreferencesStore((s) => s.activeSports)
  const sport = useMemo(() => primaryCapSportFromPrefs(activeSports), [activeSports])
  const [pendingCount, setPendingCount] = useState<number | null>(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    if (!organizationId) {
      setPendingCount(null)
      setLoading(false)
      return
    }
    let cancelled = false
    setLoading(true)
    void fetchCapWorkflowQueue(organizationId, sport)
      .then((q) => {
        if (!cancelled) setPendingCount(q.pending?.length ?? 0)
      })
      .catch(() => {
        if (!cancelled) setPendingCount(null)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [organizationId, sport])

  return (
    <div className={styles.section}>
      <div className={styles.title}>PENDING APPROVALS</div>
      {!organizationId ? (
        <CapUnlinkedNotice surface="Approvals" />
      ) : loading && pendingCount == null ? (
        <div style={{ fontFamily: 'var(--font-data)', fontSize: 12, color: 'var(--text-muted)' }}>Loading…</div>
      ) : (
        <div style={{ fontFamily: 'var(--font-data)', fontSize: 12, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          <div>
            {pendingCount == null
              ? 'Approval queue unavailable'
              : pendingCount === 0
                ? 'No deals awaiting approval'
                : `${pendingCount} deal${pendingCount === 1 ? '' : 's'} awaiting approval`}
          </div>
          <div style={{ color: 'var(--text-muted)', fontSize: 10, marginTop: 4 }}>
            <Link to="/cap/workflow" style={{ color: 'var(--accent-cyan)' }}>
              Open approvals workflow
            </Link>
          </div>
        </div>
      )}
    </div>
  )
}
