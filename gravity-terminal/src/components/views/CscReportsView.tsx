import { useEffect, useLayoutEffect, useMemo, useState } from 'react'
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
} from '../../types/reports'
import {
  DEAL_STRUCTURE_GROUPS,
  SOURCE_GROUPS,
  formatComparableConfidence,
  normalizeComparableRows,
  withLegacyOption,
} from '../../lib/cscComparables'
import { enrichKeyValueDrivers } from '../../lib/cscDriverSignals'
import {
  formatDriverMetric,
  formatNilBandEndpoints,
  formatNilRangeAligned,
  formatNilValue,
  formatScore,
} from '../../lib/formatters'
import {
  classifyConferenceTier,
  classifyConfidenceTag,
  classifyTierTag,
  conferenceTierDisplayLabel,
} from '../../lib/cscReportTags'
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

  return {
    value: {
      total_benchmark: benchmark,
      range_low: rangeLow,
      range_high: rangeHigh,
      tier_tag: benchmark != null && benchmark >= 150000 ? 'High-tier' : benchmark != null && benchmark >= 50000 ? 'Mid-tier' : 'Developing-tier',
      confidence_tag: confidenceTag,
      range_note: null,
      peer_range_applicable: true,
    },
    explanation: {
      executive_summary: `${subject} carries a Total NIL Value Benchmark of ${formatNilValue(benchmark)} with a recommended deal range of ${formatNilValue(rangeLow)} to ${formatNilValue(rangeHigh)} for roster planning context.`,
      key_value_drivers: drivers,
      driver_takeaway: `${subject}'s benchmark is most sensitive to brand and exposure signals, while proof depth and risk profile moderate upside confidence.`,
    },
    validation: {
      market_context: `Peer market context (${athlete?.conference ?? 'Conference n/a'} ${athlete?.position ?? 'Position n/a'}): peer market range ${formatNilValue(marketLow)} – ${formatNilValue(marketHigh)}; median ${formatNilValue(marketMedian)}.`,
      comparable_tier: `Comparable athletes with similar role and signal profile.`,
      example_comparables: rows.slice(0, 5),
      takeaway: `${subject}'s benchmark sits within the current comparable market envelope and should be used as a planning reference, not a single-point guarantee.`,
      comparable_state: rows.length >= 3 ? 'sufficient' : rows.length >= 1 ? 'sparse' : 'none',
      positional_reference_athletes: rows.length === 0 ? [] : [],
    },
    confidence_risk: {
      confidence_level: confidenceLevel,
      confidence_note: `${confidenceLevel} confidence based on available comparables and model signal stability.`,
      risk_level: riskLevel,
      risk_note: `${riskLevel} risk profile from latest risk component inputs.`,
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

  const selectorAthletes = useMemo(() => {
    if (!athlete) return watchlist
    const inWl = watchlist.some((a) => a.athlete_id === athlete.athlete_id)
    return inWl ? watchlist : [athlete, ...watchlist]
  }, [athlete, watchlist])

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

  useEffect(() => {
    if (!athlete) return
    if (useUiStore.getState().cscLockedFromAgent) return
    let cancelled = false
    setReportLoading(true)
    setReportError(null)
    postCscReport(athlete.athlete_id, resolvedParams)
      .then((r) => {
        if (!cancelled) {
          setReport(normalizeReport(r, athlete))
          setReportError(null)
        }
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setReport(null)
          setReportError(err instanceof Error ? err.message : 'Failed to generate report')
        }
      })
      .finally(() => {
        if (!cancelled) setReportLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [athlete, resolvedParams, cscLockedFromAgent])

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

  const low = report?.value.range_low ?? athlete?.nil_range_low
  const high = report?.value.range_high ?? athlete?.nil_range_high
  const consensus = report?.value.total_benchmark ?? athlete?.nil_valuation_consensus
  let plotPct = 50
  if (athlete && low != null && high != null && high > low && consensus != null) {
    plotPct = Math.min(100, Math.max(0, ((consensus - low) / (high - low)) * 100))
  }

  return (
    <div className={styles.grid}>
      <div className={styles.configBar}>
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
              Pick an athlete from{' '}
              <Link to="/market-scan" style={{ color: 'var(--accent-green)' }}>
                Market Scan
              </Link>{' '}
              or your watchlist to generate a CSC valuation report.
            </div>
          </div>
        ) : reportError ? (
          <div className={styles.muted} style={{ color: 'var(--accent-red)' }}>
            <div style={{ marginBottom: 8 }}>Report failed to load.</div>
            <div style={{ fontSize: 11, opacity: 0.85 }}>{reportError}</div>
            <div style={{ marginTop: 12 }}>
              <ActionButton variant="secondary" onClick={() => regen()}>
                Retry
              </ActionButton>
            </div>
          </div>
        ) : !report || reportLoading ? (
          <div className={styles.muted}>Loading report\u2026</div>
        ) : (
          <>
            {report.metadata?.model_status === 'fallback' && (
              <div className={styles.fallbackBanner}>
                Fallback scorer active{report.metadata.model_version ? ` (${report.metadata.model_version})` : ''}.
                {' '}This report is informational only and must not be used for binding decisions.
              </div>
            )}
            <GroupBreak label="// VALUE" />
            <ValueSection
              value={report.value}
              plotPct={plotPct}
              athleteName={athlete.name}
              conferenceTier={report.metadata?.conference_tier ?? null}
              cohortFallbackStep={report.metadata?.cohort_fallback_step ?? null}
              cohortFit={report.metadata?.cohort_fit ?? null}
              lowCohortData={report.metadata?.low_cohort_data ?? null}
            />
            <GroupBreak label="// EXPLANATION" />
            <ExecutiveSummarySection summary={report.explanation.executive_summary} />
            <KeyValueDriversSection
              explanation={report.explanation}
              athlete={athlete}
            />
            <GroupBreak label="// VALIDATION" />
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
            <GroupBreak label="// DETAIL" />
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
          onSelectAthlete={(id) => {
            void setActive(id)
            setSearchQ('')
            setSearchRows([])
            setSearchOpen(false)
          }}
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
  plotPct,
  athleteName,
  conferenceTier,
  cohortFallbackStep,
  cohortFit,
  lowCohortData,
}: {
  value: CscValueSection
  plotPct: number
  athleteName: string
  conferenceTier?: string | null
  cohortFallbackStep?: number | null
  cohortFit?: 'good' | 'edge' | 'poor' | null
  lowCohortData?: boolean | null
}) {
  const rangeText = formatNilRangeAligned(value.total_benchmark, value.range_low, value.range_high)
  const bandEndpoints = formatNilBandEndpoints(
    value.total_benchmark,
    value.range_low,
    value.range_high,
  )
  const confTierLabel = conferenceTierLabel(conferenceTier)
  const showLowDataChip =
    lowCohortData === true || (cohortFallbackStep != null && cohortFallbackStep >= 2)
  const showCohortFitChip = cohortFit === 'edge' || cohortFit === 'poor'
  const peerRangeApplicable = value.peer_range_applicable !== false
  const showOutlierNote = !peerRangeApplicable || cohortFit === 'poor'
  const rangeNote =
    value.range_note ||
    (showOutlierNote
      ? 'Outlier profile — peer cohort range is not applicable for deal construction. Displayed band is a deal-construction range around this athlete\'s benchmark.'
      : null)
  return (
    <div className={styles.section}>
      <div className={styles.sectionTitle}>Total NIL Value Benchmark</div>
      <div className={styles.valueHero}>{formatNilValue(value.total_benchmark)}</div>
      <div className={styles.guidelineCaption}>
        Market benchmark — guideline, not target. Use the recommended deal range
        &amp; comparables for deal construction.
      </div>
      <div className={styles.bandLabels}>
        <span>{bandEndpoints.low}</span>
        <span>{bandEndpoints.high}</span>
      </div>
      <div className={styles.bandTrack}>
        <div className={styles.bandMarker} style={{ left: `${plotPct}%` }} title={athleteName} />
      </div>
      <p className={styles.subMuted}>{rangeText}</p>
      {rangeNote && <p className={styles.prose}>{rangeNote}</p>}
      <div className={styles.tagRow}>
        {value.tier_tag && (
          <span className={`${styles.tagChip} ${tierTagClass(value.tier_tag)}`}>
            {value.tier_tag}
          </span>
        )}
        {value.confidence_tag && (
          <span className={`${styles.tagChip} ${confidenceTagClass(value.confidence_tag)}`}>
            {value.confidence_tag}
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
            title="Cohort fallback active — see Detail block for the fallback chain."
          >
            LOW DATA
          </span>
        )}
        {showCohortFitChip && (
          <span
            className={`${styles.tagChip} ${styles.tagCohortFit}`}
            title={
              cohortFit === 'poor'
                ? 'Outlier — peer cohort range is not applicable for deal construction.'
                : 'Cohort fit is weak; percentile statistics may be suppressed.'
            }
          >
            {cohortFit === 'poor' ? 'OUTLIER — PEER RANGE N/A' : `COHORT FIT: ${cohortFit?.toUpperCase()}`}
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
      <div className={styles.sectionTitle}>Executive Summary</div>
      <p className={styles.prose}>{summary}</p>
    </div>
  )
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
      <div className={styles.sectionTitleMajor}>Key Value Drivers</div>
      {drivers.map((d, idx) => (
        <div key={`${d.label}-${idx}`} className={styles.driverCard}>
          <div className={styles.driverCardHeader}>
            <span className={styles.driverLabel}>{d.label}</span>
            <span className={styles.driverSignal}>{d.signal}</span>
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
              <div className={styles.driverSignalsTitle}>Supporting Signals</div>
              <ul className={styles.driverSignalList}>
                {d.supporting_signals.map((s) => (
                  <li key={s.label}>
                    <span className={styles.driverSignalKey}>{s.label}:</span> {s.value}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {d.explanation && (
            <div className={styles.driverInterpretation}>
              <div className={styles.driverSignalsTitle}>Interpretation</div>
              <p className={styles.prose}>{d.explanation}</p>
            </div>
          )}
        </div>
      ))}
      {explanation.driver_takeaway && (
        <>
          <div className={styles.subSectionTitle}>Value Interpretation</div>
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
      <div className={styles.sectionTitleMajor}>Risk & Confidence</div>
      <div className={styles.driverRow}>
        <span className={styles.driverLabel}>Confidence</span>
        <span className={styles.driverSignal}>{confidenceRisk.confidence_level}</span>
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
        <div className={styles.sectionTitleMajor}>Market & Comparable Analysis</div>
        <p className={styles.prose}>{validation.market_context}</p>
        <p className={styles.prose}>{validation.comparable_tier}</p>
        <div className={styles.muted}>
          {validation.comparable_state === 'none'
            ? 'Direct comparables unavailable.'
            : 'No direct comparables available.'}
        </div>
        {positionalReferences.length > 0 && (
          <div className={styles.tableScroll}>
            <table className={styles.dataTable}>
              <thead>
                <tr>
                  <th>Positional Reference Athletes</th>
                  <th>GS</th>
                  <th>NIL est.</th>
                </tr>
              </thead>
              <tbody>
                {positionalReferences.map((r) => (
                  <tr key={r.athlete_id}>
                    <td>
                      <div>{r.name}</div>
                      <div className={styles.subMuted}>{r.school ?? '\u2014'}</div>
                    </td>
                    <td>{formatScore(r.gravity_score ?? null)}</td>
                    <td className={styles.amber}>{formatNilValue(r.nil_valuation_consensus)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <div className={styles.subSectionTitle}>Value Interpretation</div>
        <p className={styles.prose}>{validation.takeaway}</p>
      </div>
    )
  }
  return (
    <div className={styles.section}>
      <div className={styles.sectionTitleMajor}>Market & Comparable Analysis</div>
      <p className={styles.prose}>{validation.market_context}</p>
      <p className={styles.prose}>{validation.comparable_tier}</p>
      {validation.comparable_state === 'sparse' && (
        <div className={styles.subSectionTitle}>Sparse Comparables</div>
      )}
      <div className={styles.tableScroll}>
        <table className={styles.dataTable}>
          <thead>
            <tr>
              <th>Athlete</th>
              <th>GS</th>
              <th>Brand</th>
              <th>NIL est.</th>
              <th>Deal structure</th>
              <th>Source</th>
              <th>Conf.</th>
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
                  <td>{formatScore(r.gravity_score ?? null)}</td>
                  <td>{formatScore(r.brand_score ?? null)}</td>
                  <td className={styles.amber}>{formatNilValue(r.nil_valuation_consensus)}</td>
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
      <div className={styles.subSectionTitle}>Value Interpretation</div>
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
  return (
    <details className={styles.section}>
      <summary className={styles.sectionTitle}>Model Details</summary>
      {blocks ? (
        <div className={styles.detailBlock}>
          <div className={styles.detailLabel}>{blocks.methodology.title}</div>
          <p className={styles.prose}>{blocks.methodology.summary}</p>
          {blocks.methodology.components.length > 0 && (
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
