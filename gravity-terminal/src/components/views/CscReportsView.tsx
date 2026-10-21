import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { searchAthletesFilteredPaged } from '../../api/athletes'
import { postCscReport } from '../../api/reports'
import type {
  CscConfidenceRiskSection,
  CscDetailSection,
  CscExplanationSection,
  CscReportComparablesRow,
  CscReportJson,
  CscReportMetadata,
  CscValidationSection,
  CscValueSection,
  DealScope,
} from '../../types/reports'
import {
  DEAL_STRUCTURE_GROUPS,
  SOURCE_GROUPS,
  formatComparableConfidence,
  withLegacyOption,
} from '../../lib/cscComparables'
import { enrichKeyValueDrivers, qualifyDriverDisplay } from '../../lib/cscDriverSignals'
import {
  formatDriverMetric,
  formatNilBandEndpoints,
  formatNilValue,
  formatScore,
  plotBandPercent,
} from '../../lib/formatters'
import {
  classifyConferenceTier,
  classifyConfidenceTag,
  classifyTierTag,
  conferenceTierDisplayLabel,
} from '../../lib/cscReportTags'
import {
  hasFinalCscValuations,
  isClientPreviewValuation,
  normalizeCscReport,
} from '../../lib/cscReportNormalize'
import {
  dealConfidenceCopy,
  dealEvidenceCopy,
  dealScopeCopy,
  driverNarrativeConflictsBadge,
  modelAuditBullets,
  shouldShowTierBadge,
  titleCaseChip,
} from '../../lib/cscDealCopy'
import { downloadCscPdf } from '../../lib/pdfExport'
import { useAthleteStore } from '../../stores/athleteStore'
import { useUiStore } from '../../stores/uiStore'
import { useWatchlistStore } from '../../stores/watchlistStore'
import { ActionButton } from '../shared/ActionButton'
import { CscConfigPanel, useCscResolvedParams } from './CscConfigPanel'
import styles from './CscReportsView.module.css'

export function CscReportsView() {
  const athlete = useAthleteStore((s) => s.activeAthlete)
  const setActive = useAthleteStore((s) => s.setActiveAthlete)
  const setCscLocked = useUiStore((s) => s.setCscLockedFromAgent)
  const cscLockedFromAgent = useUiStore((s) => s.cscLockedFromAgent)
  const cscConfigOpen = useUiStore((s) => s.cscConfigOpen)
  const setCscConfigOpen = useUiStore((s) => s.setCscConfigOpen)
  const resolvedParams = useCscResolvedParams()
  const watchlist = useWatchlistStore((s) => s.athletes)

  const location = useLocation()
  const navigate = useNavigate()
  const [report, setReport] = useState<CscReportJson | null>(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [reportError, setReportError] = useState<string | null>(null)
  const [searchQ, setSearchQ] = useState('')
  const [searchRows, setSearchRows] = useState<typeof watchlist>([])
  const [searchLoading, setSearchLoading] = useState(false)
  const [searchOpen, setSearchOpen] = useState(false)

  const loadedAthleteIdRef = useRef<string | null>(null)

  const selectorAthletes = useMemo(() => {
    if (!athlete) return watchlist
    const inWl = watchlist.some((a) => a.athlete_id === athlete.athlete_id)
    return inWl ? watchlist : [athlete, ...watchlist]
  }, [athlete, watchlist])

  const selectAthlete = (id: string) => {
    void setActive(id)
    setSearchQ('')
    setSearchRows([])
    setSearchOpen(false)
  }

  useLayoutEffect(() => {
    const st = location.state as { agentCscReport?: CscReportJson } | null
    if (st?.agentCscReport) {
      setReport(normalizeCscReport(st.agentCscReport, athlete ?? null))
      navigate(`${location.pathname}${location.search}`, { replace: true, state: {} })
    }
  }, [location.state, location.pathname, location.search, navigate, athlete])

  useEffect(
    () => () => {
      setCscLocked(false)
    },
    [setCscLocked],
  )

  const athleteId = athlete?.athlete_id ?? null
  const paramsKey = JSON.stringify(resolvedParams)

  useEffect(() => {
    if (!athleteId) return
    if (useUiStore.getState().cscLockedFromAgent) return
    const current = useAthleteStore.getState().activeAthlete
    if (!current || current.athlete_id !== athleteId) return
    let cancelled = false
    const athleteChanged = loadedAthleteIdRef.current !== athleteId
    if (athleteChanged) {
      loadedAthleteIdRef.current = athleteId
      // Clear immediately — never seed athlete-card / preview dollars as the report.
      setReport(null)
    }
    setReportLoading(true)
    setReportError(null)
    postCscReport(athleteId, resolvedParams)
      .then((r) => {
        if (!cancelled) {
          const latest = useAthleteStore.getState().activeAthlete
          setReport(normalizeCscReport(r, latest?.athlete_id === athleteId ? latest : current))
          setReportError(null)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          // Keep a prior full report for this athlete if present; never invent preview valuations.
          setReport((prev) => (hasFinalCscValuations(prev) ? prev : null))
          setReportError(err instanceof Error ? err.message : 'Failed to generate report')
        }
      })
      .finally(() => {
        if (!cancelled) setReportLoading(false)
      })
    return () => {
      cancelled = true
    }
    // Fetch only when the selected athlete or report knobs change — not on
    // every realtime athlete-record tick, which previously retriggered the
    // full LLM rebuild in a loop.
  }, [athleteId, paramsKey, resolvedParams, cscLockedFromAgent])

  useEffect(() => {
    const q = searchQ.trim()
    if (!q) {
      setSearchRows([])
      setSearchOpen(false)
      return
    }
    const t = window.setTimeout(() => {
      setSearchLoading(true)
      void searchAthletesFilteredPaged({ q }, { limit: 12, offset: 0 })
        .then((page) => {
          setSearchRows(page.athletes)
          setSearchOpen(true)
        })
        .catch(() => {
          setSearchRows([])
          setSearchOpen(true)
        })
        .finally(() => setSearchLoading(false))
    }, 250)
    return () => window.clearTimeout(t)
  }, [searchQ])

  const comparables = useAthleteStore((s) => s.comparables)
  const [pdfLoading, setPdfLoading] = useState(false)
  const showFinalReport = hasFinalCscValuations(report) && !isClientPreviewValuation(report)
  const finalReport = showFinalReport ? report : null

  const regen = () => {
    if (!athlete) return
    setCscLocked(false)
    setReportLoading(true)
    setReportError(null)
    postCscReport(athlete.athlete_id, resolvedParams)
      .then((r) => {
        setReport(normalizeCscReport(r, athlete))
        setReportError(null)
      })
      .catch((err: unknown) =>
        setReportError(err instanceof Error ? err.message : 'Failed to generate report'),
      )
      .finally(() => setReportLoading(false))
  }

  const handleExportPdf = async () => {
    if (!athlete || !finalReport) return
    setPdfLoading(true)
    try {
      await downloadCscPdf(athlete, comparables, finalReport)
    } finally {
      setPdfLoading(false)
    }
  }

  return (
    <div className={styles.grid}>
      <div className={styles.configBar}>
        <div className={styles.athletePicker}>
          <input
            className={styles.athleteSearch}
            type="search"
            placeholder="Search athlete to run a report…"
            value={searchQ}
            onChange={(e) => setSearchQ(e.target.value)}
            onFocus={() => {
              if (searchRows.length > 0 || searchQ.trim()) setSearchOpen(true)
            }}
            aria-label="Search athlete to run a CSC report"
          />
          {searchOpen && (
            <div className={styles.athleteDrop} role="listbox">
              {searchLoading && <div className={styles.searchItemMuted}>Searching…</div>}
              {!searchLoading && searchRows.length === 0 && (
                <div className={styles.searchItemMuted}>No athletes found</div>
              )}
              {!searchLoading &&
                searchRows.map((a) => (
                  <button
                    key={a.athlete_id}
                    type="button"
                    className={styles.searchItem}
                    onClick={() => selectAthlete(a.athlete_id)}
                  >
                    <span>{a.name}</span>
                    <span className={styles.subMuted}>
                      {[a.school, a.position, a.conference].filter(Boolean).join(' · ')}
                    </span>
                  </button>
                ))}
            </div>
          )}
          <select
            className={styles.athleteSelect}
            value={athlete?.athlete_id ?? ''}
            onChange={(e) => {
              if (e.target.value) selectAthlete(e.target.value)
            }}
            aria-label="Select athlete"
          >
            {!athlete && <option value="">Select athlete…</option>}
            {selectorAthletes.map((a) => (
              <option key={a.athlete_id} value={a.athlete_id}>
                {a.name}
                {a.school ? ` · ${a.school}` : ''}
              </option>
            ))}
          </select>
        </div>
        <button
          type="button"
          className={styles.configToggle}
          onClick={() => setCscConfigOpen(!cscConfigOpen)}
          aria-expanded={cscConfigOpen}
        >
          {cscConfigOpen ? 'Hide configuration' : 'Configure report'}
        </button>
      </div>
      <div className={styles.preview}>
        {!athlete ? (
          <div
            className={styles.muted}
            style={{
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
              Search an athlete above, run{' '}
              <span className={styles.inlineCmd}>csc --athlete &quot;Athlete Name&quot;</span> in
              the terminal, or pick from{' '}
              <Link to="/market-scan" style={{ color: 'var(--accent-green)' }}>
                Market Scan
              </Link>
              .
            </div>
          </div>
        ) : reportError && !showFinalReport ? (
          <div className={styles.muted} style={{ color: 'var(--accent-red)' }}>
            <div style={{ marginBottom: 8 }}>Report failed to load.</div>
            <div style={{ fontSize: 11, opacity: 0.85 }}>{reportError}</div>
            <div style={{ marginTop: 12 }}>
              <ActionButton variant="secondary" onClick={() => regen()}>
                Retry
              </ActionButton>
            </div>
          </div>
        ) : reportLoading && !showFinalReport ? (
          <div className={styles.loadingState} role="status" aria-live="polite">
            <div className={styles.reportSubject}>
              <div className={styles.reportName}>{athlete.name}</div>
              <div className={styles.reportMeta}>
                {[athlete.school, athlete.position, athlete.conference].filter(Boolean).join(' · ')}
              </div>
            </div>
            <div className={styles.updatingBanner}>Building full CSC report{'\u2026'}</div>
            <p className={styles.loadingHint}>
              Suggested offer and yearly market value appear only after the full report is ready.
              Athlete-card or preliminary figures are not shown as recommendations.
            </p>
            <div className={styles.loadingSkeleton} aria-hidden="true">
              <div className={styles.skeletonBlock} />
              <div className={styles.skeletonBlock} />
              <div className={styles.skeletonBlockWide} />
            </div>
          </div>
        ) : !finalReport ? (
          <div className={styles.muted}>Loading report{'\u2026'}</div>
        ) : (
          <>
            {reportLoading && (
              <div className={styles.updatingBanner} role="status">
                Refreshing the full report{'\u2026'} Prior recommendations stay visible until the update finishes.
              </div>
            )}
            {reportError && (
              <div className={styles.fallbackBanner}>
                Live report refresh failed ({reportError}). Showing the last full report — not a preliminary estimate.{' '}
                <button type="button" className={styles.inlineRetry} onClick={() => regen()}>
                  Retry
                </button>
              </div>
            )}
            {finalReport.metadata?.model_status === 'fallback' && (
              <div className={styles.fallbackBanner}>
                Fallback scorer active{finalReport.metadata.model_version ? ` (${finalReport.metadata.model_version})` : ''}.
                {' '}This report is informational only and must not be used for binding decisions.
              </div>
            )}
            {finalReport.metadata?.roster_verification_status === 'stale' && (
              <div className={styles.fallbackBanner}>
                Roster verification is stale
                {finalReport.metadata.roster_freshness_warning
                  ? ` (${finalReport.metadata.roster_freshness_warning})`
                  : ''}.
                {' '}Refresh the authoritative roster before using this report for binding decisions.
              </div>
            )}
            <div className={styles.reportSubject}>
              <div className={styles.reportName}>{athlete.name}</div>
              <div className={styles.reportMeta}>
                {[athlete.school, athlete.position, athlete.conference].filter(Boolean).join(' · ')}
              </div>
            </div>
            <GroupBreak label="WHAT TO OFFER" />
            <ValueSection
              value={finalReport.value}
              athleteName={athlete.name}
              conferenceTier={finalReport.metadata?.conference_tier ?? null}
              cohortFallbackStep={finalReport.metadata?.cohort_fallback_step ?? null}
              cohortFit={finalReport.metadata?.cohort_fit ?? null}
              lowCohortData={finalReport.metadata?.low_cohort_data ?? null}
              dealScopeReadiness={finalReport.metadata?.deal_scope_readiness ?? null}
              cohortSize={finalReport.metadata?.cohort_size ?? null}
              comparableState={finalReport.metadata?.comparable_state ?? null}
            />
            <GroupBreak label="WHY THIS NUMBER" />
            <ExecutiveSummarySection summary={finalReport.explanation.executive_summary} />
            <KeyValueDriversSection
              explanation={finalReport.explanation}
              athlete={athlete}
            />
            <GroupBreak label="PEER CHECK" />
            <ValidationSection
              validation={finalReport.validation}
              onChange={(rows) =>
                setReport({
                  ...finalReport,
                  validation: { ...finalReport.validation, example_comparables: rows },
                })
              }
            />
            <ConfidenceRiskSection confidenceRisk={finalReport.confidence_risk} />
            <GroupBreak label="MODEL DETAIL" />
            <DetailSection detail={finalReport.detail} metadata={finalReport.metadata} />
            <ReportFooter metadata={finalReport.metadata} />
          </>
        )}
      </div>
      {cscConfigOpen && (
        <button
          type="button"
          className={styles.configBackdrop}
          aria-label="Close configuration"
          onClick={() => setCscConfigOpen(false)}
        />
      )}
      <aside className={`${styles.config} ${cscConfigOpen ? styles.configOpen : ''}`}>
        <div className={styles.configHeader}>
          <div className={styles.configTitle}>CONFIGURATION</div>
          <button
            type="button"
            className={styles.configClose}
            onClick={() => setCscConfigOpen(false)}
            aria-label="Close configuration"
          >
            ×
          </button>
        </div>
        <CscConfigPanel
          searchQ={searchQ}
          setSearchQ={setSearchQ}
          searchOpen={searchOpen}
          setSearchOpen={setSearchOpen}
          searchLoading={searchLoading}
          searchRows={searchRows}
          selectorAthletes={selectorAthletes}
          onSelectAthlete={selectAthlete}
          onRegen={regen}
          onExportPdf={() => void handleExportPdf()}
          pdfLoading={pdfLoading}
          hasReport={showFinalReport}
        />
      </aside>
    </div>
  )
}

function tierTagClass(tier: string | null | undefined): string {
  switch (classifyTierTag(tier)) {
    case 'top':
      return styles.tagTop
    case 'mid':
      return styles.tagMid
    case 'emerging':
      return styles.tagEmerging
    case 'developing':
      return styles.tagDeveloping
    default:
      return ''
  }
}

function confidenceTagClass(confidence: string | null | undefined): string {
  switch (classifyConfidenceTag(confidence)) {
    case 'high':
      return styles.tagConfHigh
    case 'moderate':
      return styles.tagConfMod
    case 'low':
      return styles.tagConfLow
    default:
      return ''
  }
}

function conferenceTierClass(tier: string | null | undefined): string {
  const token = classifyConferenceTier(tier)
  if (!token) return ''
  if (token === 'power_5' || token === 'power_4' || token === 'power_6') {
    return styles.tagPower5
  }
  return styles.tagPowerOther
}

function conferenceTierLabel(tier: string | null | undefined): string | null {
  return conferenceTierDisplayLabel(tier)
}

function ValueSection({
  value,
  athleteName,
  conferenceTier,
  cohortFallbackStep,
  cohortFit,
  lowCohortData,
  dealScopeReadiness,
  cohortSize,
  comparableState,
}: {
  value: CscValueSection
  athleteName: string
  conferenceTier?: string | null
  cohortFallbackStep?: number | null
  cohortFit?: 'good' | 'edge' | 'poor' | null
  lowCohortData?: boolean | null
  dealScopeReadiness?: string | null
  cohortSize?: number | null
  comparableState?: string | null
}) {
  const scopeOptions = value.deal_scopes ?? {}
  const [selectedScope, setSelectedScope] = useState<DealScope>(
    value.selected_deal_scope ?? 'standard_activation',
  )
  useEffect(() => {
    setSelectedScope(value.selected_deal_scope ?? 'standard_activation')
  }, [value.selected_deal_scope, value.deal_scopes])
  const scoped = scopeOptions[selectedScope]
  const activationLow = scoped?.low ?? value.activation_deal_low ?? value.range_low
  const activationMid =
    scoped?.mid ?? value.activation_deal_mid ??
    (activationLow != null && (scoped?.high ?? value.activation_deal_high ?? value.range_high) != null
      ? (activationLow + ((scoped?.high ?? value.activation_deal_high ?? value.range_high) as number)) / 2
      : null)
  const activationHigh = scoped?.high ?? value.activation_deal_high ?? value.range_high
  const plotPct = plotBandPercent(activationMid, activationLow, activationHigh)
  const bandEndpoints = formatNilBandEndpoints(
    activationMid,
    activationLow,
    activationHigh,
  )
  const scopeCopy = dealScopeCopy(selectedScope)
  const confidenceCopy = dealConfidenceCopy(scoped?.confidence ?? value.deal_confidence)
  const evidenceCopy = dealEvidenceCopy(
    scoped?.qualified_transactions,
    scoped?.readiness ?? dealScopeReadiness,
  )
  const confTierLabel = conferenceTierLabel(conferenceTier)
  const showTierBadge = shouldShowTierBadge({
    cohortSize,
    comparableState,
    lowCohortData,
  })
  const showLowDataChip =
    lowCohortData === true || (cohortFallbackStep != null && cohortFallbackStep >= 2) || !showTierBadge
  const showCohortFitChip = cohortFit === 'edge' || cohortFit === 'poor'
  const peerRangeApplicable = value.peer_range_applicable !== false
  const showOutlierNote = !peerRangeApplicable || cohortFit === 'poor'
  const rangeNote = showOutlierNote
    ? 'This athlete sits outside a typical peer set, so the band is built around their own benchmark rather than a peer envelope.'
    : null
  const yearly = formatNilValue(value.annual_nil_benchmark ?? value.total_benchmark)
  return (
    <div className={styles.section}>
      <div className={styles.sectionTitle}>Suggested offer</div>
      <p className={styles.dealLead}>
        Price for this deal with {athleteName} — not their full-year NIL value ({yearly}).
      </p>
      {Object.keys(scopeOptions).length > 0 && (
        <label className={styles.dealScopeField}>
          <span>Deal type</span>
          <select value={selectedScope} onChange={(event) => setSelectedScope(event.target.value as DealScope)}>
            {Object.values(scopeOptions).filter(Boolean).map((estimate) => (
              <option key={estimate!.scope} value={estimate!.scope}>
                {dealScopeCopy(estimate!.scope).menuLabel}
              </option>
            ))}
          </select>
        </label>
      )}
      <p className={styles.scopeHint}>{scopeCopy.blurb}</p>
      <div className={styles.offerHero}>{formatNilValue(activationMid)}</div>
      <div className={styles.offerHeroCaption}>Suggested offer · {scopeCopy.menuLabel}</div>
      <div className={styles.bandBlock}>
        <div className={styles.bandLabels}>
          <span>
            <span className={styles.bandRole}>Low</span>
            {bandEndpoints.low}
          </span>
          <span className={styles.bandMidLabel}>
            <span className={styles.bandRole}>Suggested</span>
            {formatNilValue(activationMid)}
          </span>
          <span>
            <span className={styles.bandRole}>High</span>
            {bandEndpoints.high}
          </span>
        </div>
        <div className={styles.bandTrack}>
          <div className={styles.bandMarker} style={{ left: `${plotPct}%` }} title={`${athleteName} suggested offer`} />
        </div>
      </div>
      <div className={styles.contextGrid}>
        <div className={styles.contextCard}>
          <div className={styles.dealGuidanceLabel}>Yearly market value</div>
          <div className={`${styles.contextValue} ${styles.contextValueMuted}`}>{yearly}</div>
          <div className={styles.contextHint}>
            Full-year NIL worth. Do not use this as the price of one deal.
          </div>
        </div>
        <div className={styles.contextCard}>
          <div className={styles.dealGuidanceLabel}>How sure we are</div>
          <div className={styles.contextValue}>{confidenceCopy.title}</div>
          <div className={styles.contextHint}>{confidenceCopy.detail}</div>
        </div>
        <div className={styles.contextCard}>
          <div className={styles.dealGuidanceLabel}>Evidence</div>
          <div className={styles.contextValue}>{evidenceCopy.title}</div>
          <div className={styles.contextHint}>{evidenceCopy.detail}</div>
        </div>
      </div>
      {rangeNote && <p className={styles.prose}>{rangeNote}</p>}
      <div className={styles.tagRow}>
        {showTierBadge && value.tier_tag && (
          <span className={`${styles.tagChip} ${tierTagClass(value.tier_tag)}`}>
            {titleCaseChip(value.tier_tag)}
          </span>
        )}
        {value.confidence_tag && (
          <span className={`${styles.tagChip} ${confidenceTagClass(value.confidence_tag)}`}>
            {dealConfidenceCopy(value.confidence_tag).title}
          </span>
        )}
        {confTierLabel && (
          <span className={`${styles.tagChip} ${conferenceTierClass(conferenceTier)}`}>
            {confTierLabel}
          </span>
        )}
        {showLowDataChip && (
          <span
            className={`${styles.tagChip} ${styles.tagLowData}`}
            title="Few close peers — see Model Detail for how the comparison set was built."
          >
            {titleCaseChip('Limited comps')}
          </span>
        )}
        {showCohortFitChip && (
          <span
            className={`${styles.tagChip} ${styles.tagCohortFit}`}
            title={
              cohortFit === 'poor'
                ? 'This athlete sits outside a typical peer set, so the band uses their own numbers.'
                : 'Few close peers — percentile stats may be thin.'
            }
          >
            {titleCaseChip(cohortFit === 'poor' ? 'Unusual vs peers' : 'Thin peer set')}
          </span>
        )}
      </div>
    </div>
  )
}

function GroupBreak({ label }: { label: string }) {
  return (
    <div className={styles.groupBreak} aria-hidden="true">
      <span className={styles.groupBreakLabel}>{label}</span>
    </div>
  )
}

function ExecutiveSummarySection({ summary }: { summary: string }) {
  return (
    <div className={styles.section}>
      <div className={styles.sectionTitle}>The takeaway</div>
      <p className={styles.prose}>{summary}</p>
    </div>
  )
}

function withScoreScale(label: string, value: string): string {
  if (!/score/i.test(label)) return value
  if (/\/100/.test(value)) return value
  if (/^\d+(\.\d+)?$/.test(value.trim())) return `${value.trim()}/100`
  return value
}

function KeyValueDriversSection({
  explanation,
  athlete,
}: {
  explanation: CscExplanationSection
  athlete: ReturnType<typeof useAthleteStore.getState>['activeAthlete']
}) {
  const drivers = enrichKeyValueDrivers(explanation.key_value_drivers, athlete)
  return (
    <div className={styles.section}>
      <div className={styles.sectionTitleMajor}>What drives the number</div>
      {drivers.map((d, idx) => {
        const display = qualifyDriverDisplay(d)
        const hideNarrative = driverNarrativeConflictsBadge(d.label, d.signal, d.explanation)
        return (
        <div key={`${d.label}-${idx}`} className={styles.driverCard}>
          <div className={styles.driverCardHeader}>
            <span className={styles.driverLabel}>{d.label}</span>
            <span className={styles.driverSignal}>
              {display.signal}
              {display.qualifier ? ` · ${display.qualifier}` : ''}
            </span>
          </div>
          {d.supporting_metrics && d.supporting_metrics.length > 0 && (
            <div className={styles.driverMetrics} aria-label={`${d.label} supporting metrics`}>
              {d.supporting_metrics.map((m) => (
                <div key={m.label} className={styles.driverMetricCell}>
                  <div className={styles.driverMetricValue}>
                    {formatDriverMetric(m.value, m.unit)}
                    {m.unit &&
                    !['followers', 'reach', 'count', '%', '$', 'pts', '/100', 'score', '30d'].includes(
                      m.unit.toLowerCase(),
                    ) ? (
                      <span className={styles.driverMetricUnit}>{m.unit}</span>
                    ) : null}
                  </div>
                  <div className={styles.driverMetricLabel}>{m.label}</div>
                </div>
              ))}
            </div>
          )}
          {d.supporting_signals && d.supporting_signals.length > 0 && (
            <div className={styles.driverSignals}>
              <div className={styles.driverSignalsTitle}>The numbers</div>
              <ul className={styles.driverSignalList}>
                {d.supporting_signals.map((s) => (
                  <li key={s.label}>
                    <span className={styles.driverSignalKey}>{s.label}:</span>{' '}
                    {withScoreScale(s.label, s.value)}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {d.explanation && !hideNarrative && (
            <div className={styles.driverInterpretation}>
              <div className={styles.driverSignalsTitle}>What that means</div>
              <p className={styles.prose}>{d.explanation}</p>
            </div>
          )}
        </div>
        )
      })}
      {explanation.driver_takeaway && (
        <>
          <div className={styles.subSectionTitle}>What that means</div>
          <p className={styles.prose}>{explanation.driver_takeaway}</p>
        </>
      )}
    </div>
  )
}

function ConfidenceRiskSection({
  confidenceRisk,
}: {
  confidenceRisk: CscConfidenceRiskSection
}) {
  return (
    <div className={styles.section}>
      <div className={styles.sectionTitleMajor}>Risk</div>
      <div className={styles.driverRow}>
        <span className={styles.driverLabel}>Confidence</span>
        <span className={styles.driverSignal}>{dealConfidenceCopy(confidenceRisk.confidence_level).title}</span>
        <span className={styles.subMuted}>{confidenceRisk.confidence_note}</span>
      </div>
      <div className={styles.driverRow}>
        <span className={styles.driverLabel}>Risk</span>
        <span className={styles.driverSignal}>{confidenceRisk.risk_level}</span>
        <span className={styles.subMuted}>{confidenceRisk.risk_note}</span>
      </div>
    </div>
  )
}

function ValidationSection({
  validation,
  onChange,
}: {
  validation: CscValidationSection
  onChange: (rows: CscReportComparablesRow[]) => void
}) {
  const list = validation.example_comparables ?? []
  const positionalReferences = validation.positional_reference_athletes ?? []
  if (list.length === 0) {
    return (
      <div className={styles.section}>
        <div className={styles.sectionTitleMajor}>How this compares</div>
        <p className={styles.prose}>{validation.market_context}</p>
        <p className={styles.prose}>{validation.comparable_tier}</p>
        <div className={styles.muted}>No similar athletes on file yet.</div>
        {positionalReferences.length > 0 && (
          <div className={styles.tableScroll}>
            <table className={styles.dataTable}>
              <thead>
                <tr>
                  <th>Similar athletes</th>
                  <th>Gravity</th>
                  <th>Yearly NIL</th>
                </tr>
              </thead>
              <tbody>
                {positionalReferences.map((r) => (
                  <tr key={r.athlete_id}>
                    <td>
                      <div>{r.name}</div>
                      <div className={styles.subMuted}>{r.school ?? '\u2014'}</div>
                    </td>
                    <td className={styles.tdNum}>{formatScore(r.gravity_score ?? null)}</td>
                    <td className={`${styles.amber} ${styles.tdNum}`}>{formatNilValue(r.nil_valuation_consensus)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className={styles.subSectionTitle}>What that means</div>
        <p className={styles.prose}>{validation.takeaway}</p>
      </div>
    )
  }
  return (
    <div className={styles.section}>
        <div className={styles.sectionTitleMajor}>How this compares</div>
      <p className={styles.prose}>{validation.market_context}</p>
      <p className={styles.prose}>{validation.comparable_tier}</p>
      {validation.comparable_state === 'sparse' && (
        <div className={styles.subSectionTitle}>Few direct comps</div>
      )}
      <div className={styles.tableScroll}>
        <table className={styles.dataTable}>
          <thead>
            <tr>
              <th>Athlete</th>
              <th className={styles.tdNum}>Gravity</th>
              <th className={styles.tdNum}>Brand</th>
              <th className={styles.tdNum}>Yearly NIL</th>
              <th>Deal structure</th>
              <th>Source</th>
              <th>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {list.map((r) => {
              const dealSelection = withLegacyOption(DEAL_STRUCTURE_GROUPS, r.deal_structure)
              const sourceSelection = withLegacyOption(SOURCE_GROUPS, r.verified_source)
              return (
                <tr key={r.athlete_id}>
                  <td>
                    <div>{r.name}</div>
                    <div className={styles.subMuted}>
                      {r.school ?? '\u2014'} · {r.position ?? '\u2014'}
                    </div>
                  </td>
                    <td className={styles.tdNum}>{formatScore(r.gravity_score ?? null)}</td>
                    <td className={styles.tdNum}>{formatScore(r.brand_score ?? null)}</td>
                    <td className={`${styles.amber} ${styles.tdNum}`}>{formatNilValue(r.nil_valuation_consensus)}</td>
                  <td>
                    <select
                      className={styles.cellSelect}
                      value={dealSelection.value}
                      onChange={(e) => {
                        const next = list.map((x) =>
                          x.athlete_id === r.athlete_id ? { ...x, deal_structure: e.target.value } : x,
                        )
                        onChange(next)
                      }}
                    >
                      {dealSelection.groups.map((group) => (
                        <optgroup key={group.label} label={group.label}>
                          {group.options.map((option) => (
                            <option key={option} value={option}>
                              {option}
                            </option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                  </td>
                  <td>
                    <select
                      className={styles.cellSelect}
                      value={sourceSelection.value}
                      onChange={(e) => {
                        const next = list.map((x) =>
                          x.athlete_id === r.athlete_id ? { ...x, verified_source: e.target.value } : x,
                        )
                        onChange(next)
                      }}
                    >
                      {sourceSelection.groups.map((group) => (
                        <optgroup key={group.label} label={group.label}>
                          {group.options.map((option) => (
                            <option key={option} value={option}>
                              {option}
                            </option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                  </td>
                  <td>{formatComparableConfidence(r.confidence)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
      <div className={styles.subSectionTitle}>What that means</div>
      <p className={styles.prose}>{validation.takeaway}</p>
    </div>
  )
}

function ReportFooter({ metadata }: { metadata: CscReportMetadata }) {
  const reportId = metadata?.report_id ?? null
  return (
    <div className={styles.section}>
      <div className={styles.subSectionTitle}>Disclaimer</div>
      <p className={styles.prose} style={{ fontSize: 12, marginBottom: 6 }}>
        This is a commercial intelligence estimate used to inform NIL valuation discussions; it is not
        legal, tax, or financial advice. Final NIL agreement terms remain subject to House v. NCAA
        settlement compliance review and the College Sports Commission (CSC) Deal Approval process.
        Gravity Score is not the deal counterparty and is not liable for decisions made from this report's outputs.
      </p>
      {reportId && (
        <p className={styles.subMuted} style={{ fontFamily: 'var(--font-data)' }}>
          Report ID: {reportId}
        </p>
      )}
    </div>
  )
}

function DetailSection({ detail, metadata }: { detail: CscDetailSection; metadata: CscReportMetadata }) {
  const blocks = detail.blocks ?? null
  const audit = modelAuditBullets(metadata, detail)
  return (
    <details className={styles.section}>
      <summary className={styles.sectionTitle}>Model Details</summary>
      <div className={styles.detailBlock}>
        <div className={styles.detailLabel}>Audit trail</div>
        <ul className={styles.prose} style={{ paddingLeft: 18, margin: '0 0 12px' }}>
          {audit.map((row) => (
            <li key={row}>{row}</li>
          ))}
        </ul>
      </div>
      {blocks ? (
        <div className={styles.detailBlock}>
          <div className={styles.detailLabel}>{blocks.methodology.title}</div>
          <p className={styles.prose}>{blocks.methodology.summary}</p>
          {blocks.methodology.components.length > 0 &&
            !blocks.methodology.components[0]?.toLowerCase().startsWith('model version') && (
            <ul className={styles.prose} style={{ paddingLeft: 18, margin: 0 }}>
              {blocks.methodology.components.map((row, idx) => (
                <li key={idx}>{row}</li>
              ))}
            </ul>
          )}
          <div className={styles.detailLabel}>{blocks.cohort.title}</div>
          <p className={styles.prose}>
            {blocks.cohort.sport} · {blocks.cohort.position_group} · {blocks.cohort.conference ?? 'n/a'}
            {blocks.cohort.conference_tier ? ` (${blocks.cohort.conference_tier})` : ''}
            {'\n'}n={blocks.cohort.size} · window={blocks.cohort.window_days}d · season={blocks.cohort.season_state ?? 'n/a'} · fallback_step={blocks.cohort.fallback_step}
          </p>
          <div className={styles.detailLabel}>{blocks.comparables.title}</div>
          <p className={styles.prose}>
            state={blocks.comparables.state}
            {blocks.comparables.computed_at ? ` · computed_at=${blocks.comparables.computed_at}` : ''}
          </p>
          <div className={styles.detailLabel}>{blocks.provenance.title}</div>
          <p className={styles.prose}>
            report_id={blocks.provenance.report_id} · tier_version={blocks.provenance.tier_version} · rollout_phase={blocks.provenance.rollout_phase}
            {'\n'}exposure_formula_version={blocks.provenance.exposure_formula_version}
            {blocks.provenance.model_version
              ? ` · model_version=${blocks.provenance.model_version} (${blocks.provenance.model_status ?? 'production'})`
              : ''}
          </p>
          <div className={styles.detailLabel}>{blocks.shap_attribution.title}</div>
          {blocks.shap_attribution.narrative && (
            <p className={styles.prose}>{blocks.shap_attribution.narrative}</p>
          )}
          {blocks.shap_attribution.rows.length > 0 && (
            <table className={styles.dataTable}>
              <thead>
                <tr>
                  <th>Feature</th>
                  <th>Contribution</th>
                </tr>
              </thead>
              <tbody>
                {blocks.shap_attribution.rows.map((row) => (
                  <tr key={row.feature}>
                    <td>{row.feature}</td>
                    <td>{row.contribution.toFixed(3)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : (
        <div className={styles.detailBlock}>
          <div className={styles.detailLabel}>SHAP Attribution</div>
          <p className={styles.prose}>{detail.shap_attribution}</p>
          <div className={styles.detailLabel}>Methodology</div>
          <p className={styles.prose}>{detail.methodology}</p>
          <div className={styles.detailLabel}>Inputs</div>
          <p className={styles.prose}>{detail.inputs}</p>
          <div className={styles.detailLabel}>Provenance</div>
          <p className={styles.prose}>
            tier_version={metadata.tier_version} · cohort_window_days={metadata.cohort_window_days_used} · season_state={metadata.season_state}
            {'\n'}cohort_size={metadata.cohort_size} · fallback_step={metadata.cohort_fallback_step} · comparable_state={metadata.comparable_state}
            {'\n'}comparable_sets_computed_at={metadata.comparable_sets_computed_at ?? 'n/a'} · exposure_formula_version={metadata.exposure_formula_version}
          </p>
        </div>
      )}
    </details>
  )
}
