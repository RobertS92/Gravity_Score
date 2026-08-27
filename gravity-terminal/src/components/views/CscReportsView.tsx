import { useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { searchAthletesFilteredPaged } from '../../api/athletes'
import { postCscReport } from '../../api/reports'
import type {
  CscConfidenceRiskSection,
  CscDetailSection,
  CscExplanationSection,
  CscKeyValueDriver,
  CscReportMetadata,
  CscReportComparablesRow,
  CscReportJson,
  CscValidationSection,
  CscValueSection,
  DealScope,
} from '../../types/reports'
import {
  DEAL_STRUCTURE_GROUPS,
  SOURCE_GROUPS,
  formatComparableConfidence,
  normalizeComparableRows,
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
  dealConfidenceCopy,
  dealEvidenceCopy,
  dealScopeCopy,
  driverNarrativeConflictsBadge,
  fallbackTakeaway,
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

function withDefaultText(value: string | null | undefined, fallback: string) {
  const clean = (value ?? '').trim()
  return clean.length > 0 ? clean : fallback
}

function normalizeComparables(rows: CscReportComparablesRow[] | undefined): CscReportComparablesRow[] {
  return normalizeComparableRows(rows).slice(0, 12)
}

function levelFromScore(value: number | null | undefined, invert = false): 'High' | 'Moderate' | 'Low' {
  if (value == null || Number.isNaN(value)) return 'Moderate'
  const adjusted = invert ? 100 - value : value
  if (adjusted >= 66) return 'High'
  if (adjusted >= 40) return 'Moderate'
  return 'Low'
}

function fallbackActivationBand(annual: number | null | undefined): {
  low: number | null
  mid: number | null
  high: number | null
} {
  if (annual == null || !Number.isFinite(annual) || annual <= 0) {
    return { low: null, mid: null, high: null }
  }
  const mid = Math.max(500, annual * 0.016)
  return { low: mid * 0.48, mid, high: mid * 1.75 }
}

function buildFallbackDrivers(athlete: ReturnType<typeof useAthleteStore.getState>['activeAthlete']): CscKeyValueDriver[] {
  return [
    {
      label: 'Brand Strength',
      signal: levelFromScore(athlete?.brand_score),
      explanation: `Brand score ${formatScore(athlete?.brand_score ?? null)} relative to peers.`,
    },
    {
      label: 'Market Proof',
      signal: levelFromScore(athlete?.proof_score),
      explanation: `Proof score ${formatScore(athlete?.proof_score ?? null)} with current verified activity.`,
    },
    {
      label: 'Exposure',
      signal: levelFromScore(athlete?.proximity_score),
      explanation: `Exposure score ${formatScore(athlete?.proximity_score ?? null)} for program/media visibility.`,
    },
    {
      label: 'Risk',
      signal: levelFromScore(athlete?.risk_score, true),
      explanation: `Risk score ${formatScore(athlete?.risk_score ?? null)} impacts valuation certainty.`,
    },
  ]
}

function buildFallbackReport(
  athlete: ReturnType<typeof useAthleteStore.getState>['activeAthlete'],
  rows: CscReportComparablesRow[] = [],
): CscReportJson {
  const athleteName = athlete?.name
  const subject = athleteName ?? 'the selected athlete'
  const benchmark = athlete?.nil_valuation_consensus ?? athlete?.dollar_p50_usd ?? null
  const rangeLow = athlete?.nil_range_low ?? athlete?.dollar_p10_usd ?? null
  const rangeHigh = athlete?.nil_range_high ?? athlete?.dollar_p90_usd ?? null
  const confidenceLevel = levelFromScore((athlete?.dollar_confidence?.dollar_confidence_score ?? null) != null
    ? (athlete?.dollar_confidence?.dollar_confidence_score ?? 0) * 100
    : null)
  const confidenceTag = `${confidenceLevel} Confidence`
  const riskLevel = levelFromScore(athlete?.risk_score ?? null, true)
  const drivers = buildFallbackDrivers(athlete)
  const marketValues = rows.map((r) => r.nil_valuation_consensus).filter((v): v is number => v != null)
  const marketLow = marketValues.length ? Math.min(...marketValues) : rangeLow
  const marketHigh = marketValues.length ? Math.max(...marketValues) : rangeHigh
  const marketMedian = marketValues.length
    ? [...marketValues].sort((a, b) => a - b)[Math.floor(marketValues.length / 2)]
    : benchmark
  const activation = fallbackActivationBand(benchmark)

  return {
    value: {
      total_benchmark: benchmark,
      range_low: activation.low,
      range_high: activation.high,
      annual_nil_benchmark: benchmark,
      activation_deal_low: activation.low,
      activation_deal_mid: activation.mid,
      activation_deal_high: activation.high,
      season_partnership_low: null,
      season_partnership_high: null,
      deal_confidence: confidenceLevel,
      deal_uncertainty: null,
      deal_pricing_method: 'legacy_fallback',
      deal_pricing_basis: 'Preview using current athlete numbers. The full report will refine the campaign range.',
      selected_deal_scope: 'standard_activation',
      deal_scopes: {
        standard_activation: {
          scope: 'standard_activation',
          label: 'Standard activation',
          low: activation.low,
          mid: activation.mid,
          high: activation.high,
          model_version: 'activation_prior_v2',
          calibrated: false,
          confidence: 'Uncalibrated',
          basis: 'Preview from this athlete’s current numbers while the full report loads.',
          qualified_transactions: 0,
          validation_transactions: 0,
          empirical_coverage: null,
          target_coverage: null,
          median_absolute_percentage_error: null,
          evaluated_through: null,
          readiness: 'insufficient_data',
        },
      },
      tier_tag: benchmark != null && benchmark >= 150000 ? 'High-tier' : benchmark != null && benchmark >= 50000 ? 'Mid-tier' : 'Developing-tier',
      confidence_tag: confidenceTag,
      range_note: null,
      peer_range_applicable: true,
    },
    explanation: {
      executive_summary: fallbackTakeaway(
        subject,
        formatNilValue(benchmark),
        formatNilValue(activation.low),
        formatNilValue(activation.high),
      ),
      key_value_drivers: drivers,
      driver_takeaway: `${subject}'s offer is driven most by brand and exposure. Proof and risk decide how firmly you can hold the number.`,
    },
    validation: {
      market_context: `Peers at ${athlete?.conference ?? 'this conference'} ${athlete?.position ?? 'this position'}: yearly values from ${formatNilValue(marketLow)} to ${formatNilValue(marketHigh)} (median ${formatNilValue(marketMedian)}).`,
      comparable_tier: 'Athletes with a similar role and signal profile.',
      example_comparables: rows.slice(0, 5),
      takeaway: `Use ${subject}'s yearly value as context. Price the deal from the campaign range, not the yearly number.`,
      comparable_state: rows.length >= 3 ? 'sufficient' : rows.length >= 1 ? 'sparse' : 'none',
      positional_reference_athletes: rows.length === 0 ? [] : [],
    },
    confidence_risk: {
      confidence_level: confidenceLevel,
      confidence_note: `${confidenceLevel} confidence from the signals and comps we have so far.`,
      risk_level: riskLevel,
      risk_note: `${riskLevel} risk from roster status and modeled risk posture.`,
    },
    detail: {
      shap_attribution: 'SHAP attribution pending latest explainable model output.',
      methodology: 'Comparable-weighted NIL banding with Gravity score components and verified market observations.',
      inputs: 'Inputs include sport, position, comparables set, confidence threshold, and current score components.',
    },
    metadata: {
      tier_version: 'tier_v1',
      tier_v1: 'Developing',
      tier_v2: 'Developing',
      cohort_window_days_used: 21,
      season_state: 'unknown',
      cohort_size: rows.length,
      cohort_fallback_step: 3,
      comparable_state: rows.length >= 3 ? 'sufficient' : rows.length >= 1 ? 'sparse' : 'none',
      comparable_sets_computed_at: null,
      exposure_formula_version: 'exposure_formula_v1',
      exposure_formula_weights: { proximity_weight: 0.6, velocity_weight: 0.4 },
      rollout_phase: 'phase1',
      low_cohort_data: true,
      athlete_benchmark_percentile_in_cohort: null,
    },
    executive_summary: '',
    gravity_score_table: '',
    comparables_analysis: rows,
    nil_range_note: '',
    shap_narrative: '',
    risk_assessment: '',
    methodology: '',
  }
}

function normalizeReport(
  report: CscReportJson | null | undefined,
  athlete: ReturnType<typeof useAthleteStore.getState>['activeAthlete'],
): CscReportJson {
  const legacyRows = normalizeComparables(report?.comparables_analysis)
  const fallback = buildFallbackReport(athlete, legacyRows)
  if (!report) return fallback
  const legacyExec = withDefaultText(report.executive_summary, fallback.explanation.executive_summary)
  const legacyMethod = withDefaultText(report.methodology, fallback.detail.methodology)
  const legacyShap = withDefaultText(report.shap_narrative, fallback.detail.shap_attribution)
  const legacyRisk = withDefaultText(report.risk_assessment, fallback.confidence_risk.risk_note)
  const value: CscValueSection = {
    total_benchmark: report.value?.total_benchmark ?? fallback.value.total_benchmark,
    range_low: report.value?.range_low ?? fallback.value.range_low,
    range_high: report.value?.range_high ?? fallback.value.range_high,
    annual_nil_benchmark:
      report.value?.annual_nil_benchmark ?? report.value?.total_benchmark ?? fallback.value.annual_nil_benchmark,
    activation_deal_low:
      report.value?.activation_deal_low ?? report.value?.range_low ?? fallback.value.activation_deal_low,
    activation_deal_mid:
      report.value?.activation_deal_mid ??
      (report.value?.range_low != null && report.value?.range_high != null
        ? (report.value.range_low + report.value.range_high) / 2
        : fallback.value.activation_deal_mid),
    activation_deal_high:
      report.value?.activation_deal_high ?? report.value?.range_high ?? fallback.value.activation_deal_high,
    season_partnership_low:
      report.value?.season_partnership_low ?? fallback.value.season_partnership_low ?? null,
    season_partnership_high:
      report.value?.season_partnership_high ?? fallback.value.season_partnership_high ?? null,
    deal_confidence: report.value?.deal_confidence ?? fallback.value.deal_confidence ?? null,
    deal_uncertainty: report.value?.deal_uncertainty ?? fallback.value.deal_uncertainty ?? null,
    deal_pricing_method: report.value?.deal_pricing_method ?? fallback.value.deal_pricing_method ?? null,
    deal_pricing_basis: report.value?.deal_pricing_basis ?? fallback.value.deal_pricing_basis ?? null,
    selected_deal_scope: report.value?.selected_deal_scope,
    deal_scopes: report.value?.deal_scopes,
    tier_tag: report.value?.tier_tag ?? fallback.value.tier_tag,
    confidence_tag: report.value?.confidence_tag ?? fallback.value.confidence_tag,
    range_note: report.value?.range_note ?? fallback.value.range_note ?? null,
    peer_range_applicable:
      report.value?.peer_range_applicable ?? fallback.value.peer_range_applicable ?? true,
  }
  const explanation: CscExplanationSection = {
    executive_summary: withDefaultText(report.explanation?.executive_summary, legacyExec),
    key_value_drivers: report.explanation?.key_value_drivers?.length
      ? report.explanation.key_value_drivers
      : fallback.explanation.key_value_drivers,
    driver_takeaway: withDefaultText(
      report.explanation?.driver_takeaway,
      fallback.explanation.driver_takeaway,
    ),
  }
  const validationRows = report.validation?.example_comparables?.length
    ? normalizeComparables(report.validation.example_comparables)
    : legacyRows.length
      ? legacyRows
      : fallback.validation.example_comparables
  const validation: CscValidationSection = {
    market_context: withDefaultText(report.validation?.market_context, fallback.validation.market_context),
    comparable_tier: withDefaultText(report.validation?.comparable_tier, fallback.validation.comparable_tier),
    example_comparables: validationRows,
    takeaway: withDefaultText(report.validation?.takeaway, fallback.validation.takeaway),
    comparable_state: report.validation?.comparable_state ?? fallback.validation.comparable_state,
    positional_reference_athletes:
      report.validation?.positional_reference_athletes ?? fallback.validation.positional_reference_athletes,
  }
  const confidenceRisk: CscConfidenceRiskSection = {
    confidence_level: report.confidence_risk?.confidence_level ?? fallback.confidence_risk.confidence_level,
    confidence_note: withDefaultText(report.confidence_risk?.confidence_note, fallback.confidence_risk.confidence_note),
    risk_level: report.confidence_risk?.risk_level ?? fallback.confidence_risk.risk_level,
    risk_note: withDefaultText(report.confidence_risk?.risk_note, legacyRisk),
  }
  const detail: CscDetailSection = {
    shap_attribution: withDefaultText(report.detail?.shap_attribution, legacyShap),
    methodology: withDefaultText(report.detail?.methodology, legacyMethod),
    inputs: withDefaultText(report.detail?.inputs, fallback.detail.inputs),
    // Pass through the structured detail.blocks so the SHAP table,
    // cohort metadata, and provenance render from the live API
    // instead of silently falling back to the flat strings above.
    blocks: report.detail?.blocks ?? undefined,
  }
  const metadata: CscReportMetadata = {
    tier_version: report.metadata?.tier_version ?? fallback.metadata.tier_version,
    tier_v1: report.metadata?.tier_v1 ?? fallback.metadata.tier_v1,
    tier_v2: report.metadata?.tier_v2 ?? fallback.metadata.tier_v2,
    cohort_window_days_used: report.metadata?.cohort_window_days_used ?? fallback.metadata.cohort_window_days_used,
    season_state: report.metadata?.season_state ?? fallback.metadata.season_state,
    cohort_size: report.metadata?.cohort_size ?? fallback.metadata.cohort_size,
    cohort_fallback_step: report.metadata?.cohort_fallback_step ?? fallback.metadata.cohort_fallback_step,
    comparable_state: report.metadata?.comparable_state ?? fallback.metadata.comparable_state,
    comparable_sets_computed_at: report.metadata?.comparable_sets_computed_at ?? null,
    exposure_formula_version: report.metadata?.exposure_formula_version ?? fallback.metadata.exposure_formula_version,
    exposure_formula_weights: report.metadata?.exposure_formula_weights ?? fallback.metadata.exposure_formula_weights,
    rollout_phase: report.metadata?.rollout_phase ?? fallback.metadata.rollout_phase,
    low_cohort_data: report.metadata?.low_cohort_data ?? fallback.metadata.low_cohort_data,
    athlete_benchmark_percentile_in_cohort:
      report.metadata?.athlete_benchmark_percentile_in_cohort ?? fallback.metadata.athlete_benchmark_percentile_in_cohort,
    selected_deal_scope: report.metadata?.selected_deal_scope,
    deal_scope_calibrated: report.metadata?.deal_scope_calibrated,
    deal_scope_readiness: report.metadata?.deal_scope_readiness,
  }
  return {
    value,
    explanation,
    validation,
    confidence_risk: confidenceRisk,
    detail,
    metadata,
    executive_summary: report.executive_summary,
    gravity_score_table: report.gravity_score_table,
    comparables_analysis: report.comparables_analysis,
    nil_range_note: report.nil_range_note,
    shap_narrative: report.shap_narrative,
    risk_assessment: report.risk_assessment,
    methodology: report.methodology,
  }
}

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
      setReport(normalizeReport(st.agentCscReport, athlete ?? null))
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
      setReport(normalizeReport(null, current))
    }
    setReportLoading(true)
    setReportError(null)
    postCscReport(athleteId, resolvedParams)
      .then((r) => {
        if (!cancelled) {
          const latest = useAthleteStore.getState().activeAthlete
          setReport(normalizeReport(r, latest?.athlete_id === athleteId ? latest : current))
          setReportError(null)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setReport((prev) => prev ?? normalizeReport(null, current))
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

  const regen = () => {
    if (!athlete) return
    setCscLocked(false)
    setReportLoading(true)
    setReportError(null)
    postCscReport(athlete.athlete_id, resolvedParams)
      .then((r) => {
        setReport(normalizeReport(r, athlete))
        setReportError(null)
      })
      .catch((err: unknown) =>
        setReportError(err instanceof Error ? err.message : 'Failed to generate report'),
      )
      .finally(() => setReportLoading(false))
  }

  const handleExportPdf = async () => {
    if (!athlete) return
    setPdfLoading(true)
    try {
      await downloadCscPdf(athlete, comparables, report)
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
        ) : reportError && !report ? (
          <div className={styles.muted} style={{ color: 'var(--accent-red)' }}>
            <div style={{ marginBottom: 8 }}>Report failed to load.</div>
            <div style={{ fontSize: 11, opacity: 0.85 }}>{reportError}</div>
            <div style={{ marginTop: 12 }}>
              <ActionButton variant="secondary" onClick={() => regen()}>
                Retry
              </ActionButton>
            </div>
          </div>
        ) : !report ? (
          <div className={styles.muted}>Loading report{'\u2026'}</div>
        ) : (
          <>
            {reportLoading && (
              <div className={styles.updatingBanner} role="status">
                Loading the full report{'\u2026'}
              </div>
            )}
            {reportError && (
              <div className={styles.fallbackBanner}>
                Live report refresh failed ({reportError}). Showing the latest available numbers.{' '}
                <button type="button" className={styles.inlineRetry} onClick={() => regen()}>
                  Retry
                </button>
              </div>
            )}
            {report.metadata?.model_status === 'fallback' && (
              <div className={styles.fallbackBanner}>
                Fallback scorer active{report.metadata.model_version ? ` (${report.metadata.model_version})` : ''}.
                {' '}This report is informational only and must not be used for binding decisions.
              </div>
            )}
            {report.metadata?.roster_verification_status === 'stale' && (
              <div className={styles.fallbackBanner}>
                Roster verification is stale
                {report.metadata.roster_freshness_warning
                  ? ` (${report.metadata.roster_freshness_warning})`
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
              value={report.value}
              athleteName={athlete.name}
              conferenceTier={report.metadata?.conference_tier ?? null}
              cohortFallbackStep={report.metadata?.cohort_fallback_step ?? null}
              cohortFit={report.metadata?.cohort_fit ?? null}
              lowCohortData={report.metadata?.low_cohort_data ?? null}
              dealScopeReadiness={report.metadata?.deal_scope_readiness ?? null}
              cohortSize={report.metadata?.cohort_size ?? null}
              comparableState={report.metadata?.comparable_state ?? null}
            />
            <GroupBreak label="WHY THIS NUMBER" />
            <ExecutiveSummarySection summary={report.explanation.executive_summary} />
            <KeyValueDriversSection
              explanation={report.explanation}
              athlete={athlete}
            />
            <GroupBreak label="PEER CHECK" />
            <ValidationSection
              validation={report.validation}
              onChange={(rows) =>
                setReport({
                  ...report,
                  validation: { ...report.validation, example_comparables: rows },
                })
              }
            />
            <ConfidenceRiskSection confidenceRisk={report.confidence_risk} />
            <GroupBreak label="MODEL DETAIL" />
            <DetailSection detail={report.detail} metadata={report.metadata} />
            <ReportFooter metadata={report.metadata} />
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
          hasReport={!!report}
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
