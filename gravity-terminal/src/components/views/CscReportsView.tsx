import { useEffect, useLayoutEffect, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { postCscReport } from '../../api/reports'
import type { CscReportComparablesRow, CscReportJson } from '../../types/reports'
import { formatNilMillions, formatScore } from '../../lib/formatters'
import { downloadCscPdf } from '../../lib/pdfExport'
import { useAthleteStore } from '../../stores/athleteStore'
import { useUiStore } from '../../stores/uiStore'
import { useWatchlistStore } from '../../stores/watchlistStore'
import { ActionButton } from '../shared/ActionButton'
import styles from './CscReportsView.module.css'

const SPORTS = ['CFB', 'NCAAB', 'NCAAWB'] as const

export function CscReportsView() {
  const athlete = useAthleteStore((s) => s.activeAthlete)
  const setActive = useAthleteStore((s) => s.setActiveAthlete)
  const reportConfig = useUiStore((s) => s.reportConfig)
  const setReportConfig = useUiStore((s) => s.setReportConfig)
  const setCscLocked = useUiStore((s) => s.setCscLockedFromAgent)
  const cscLockedFromAgent = useUiStore((s) => s.cscLockedFromAgent)
  const watchlist = useWatchlistStore((s) => s.athletes)

  const location = useLocation()
  const navigate = useNavigate()
  const [report, setReport] = useState<CscReportJson | null>(null)
  const [reportLoading, setReportLoading] = useState(false)
  const [reportError, setReportError] = useState<string | null>(null)

  const selectorAthletes = useMemo(() => {
    if (!athlete) return watchlist
    const inWl = watchlist.some((a) => a.athlete_id === athlete.athlete_id)
    return inWl ? watchlist : [athlete, ...watchlist]
  }, [athlete, watchlist])

  useLayoutEffect(() => {
    const st = location.state as { agentCscReport?: CscReportJson } | null
    if (st?.agentCscReport) {
      setReport(st.agentCscReport)
      navigate(`${location.pathname}${location.search}`, { replace: true, state: {} })
    }
  }, [location.state, location.pathname, location.search, navigate])

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
    postCscReport(athlete.athlete_id, reportConfig)
      .then((r) => {
        if (!cancelled) {
          setReport(r)
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
  }, [athlete, reportConfig, cscLockedFromAgent])

  const comparables = useAthleteStore((s) => s.comparables)
  const [pdfLoading, setPdfLoading] = useState(false)

  const regen = () => {
    if (!athlete) return
    setCscLocked(false)
    setReportLoading(true)
    setReportError(null)
    postCscReport(athlete.athlete_id, reportConfig)
      .then((r) => {
        setReport(r)
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

  if (!athlete) {
    return (
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
    )
  }

  const low = athlete.nil_range_low
  const high = athlete.nil_range_high
  const consensus = athlete.nil_valuation_consensus
  let plotPct = 50
  if (low != null && high != null && high > low && consensus != null) {
    plotPct = Math.min(100, Math.max(0, ((consensus - low) / (high - low)) * 100))
  }

  return (
    <div className={styles.grid}>
      <div className={styles.preview}>
        {reportError ? (
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
            <Section title="Executive Summary" value={report.executive_summary} onChange={(v) => setReport({ ...report, executive_summary: v })} />
            <Section title="Gravity Score Summary" value={report.gravity_score_table} onChange={(v) => setReport({ ...report, gravity_score_table: v })} />
            <ComparablesSection rows={report.comparables_analysis} onChange={(rows) => setReport({ ...report, comparables_analysis: rows })} />
            <NilRangeSection note={report.nil_range_note} plotPct={plotPct} low={low} high={high} consensus={consensus} athleteName={athlete.name} />
            <Section title="SHAP Attribution Narrative" value={report.shap_narrative} onChange={(v) => setReport({ ...report, shap_narrative: v })} />
            <Section title="Risk Assessment" value={report.risk_assessment} onChange={(v) => setReport({ ...report, risk_assessment: v })} />
            <Section title="Methodology" value={report.methodology} onChange={(v) => setReport({ ...report, methodology: v })} />
          </>
        )}
      </div>
      <aside className={styles.config}>
        <div className={styles.configTitle}>CONFIGURATION</div>
        <label className={styles.field}>
          Athlete
          <select
            className={styles.select}
            value={athlete.athlete_id}
            onChange={(e) => void setActive(e.target.value)}
          >
            {selectorAthletes.map((a) => (
              <option key={a.athlete_id} value={a.athlete_id}>
                {a.name}
                {a.school ? ` · ${a.school}` : ''}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.field}>
          Sport
          <select
            className={styles.select}
            value={reportConfig.sport ?? ''}
            onChange={(e) => setReportConfig({ sport: e.target.value || undefined })}
          >
            <option value="">All</option>
            {SPORTS.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.field}>
          Position (filter)
          <input
            className={styles.textIn}
            type="text"
            placeholder="e.g. WR"
            value={reportConfig.position ?? ''}
            onChange={(e) => setReportConfig({ position: e.target.value || undefined })}
          />
        </label>
        <label className={styles.field}>
          Comparables (5–25)
          <input
            type="range"
            min={5}
            max={25}
            value={reportConfig.comparables_count ?? 12}
            onChange={(e) => setReportConfig({ comparables_count: Number(e.target.value) })}
          />
          <span className={styles.mono}>{reportConfig.comparables_count ?? 12}</span>
        </label>
        <label className={styles.field}>
          Confidence min
          <input
            type="range"
            min={50}
            max={99}
            value={Math.round((reportConfig.confidence_min ?? 0.75) * 100)}
            onChange={(e) => setReportConfig({ confidence_min: Number(e.target.value) / 100 })}
          />
        </label>
        <label className={styles.field}>
          CSC band low % (percentile)
          <input
            type="range"
            min={5}
            max={90}
            value={reportConfig.csc_band_low_pct ?? 25}
            onChange={(e) => setReportConfig({ csc_band_low_pct: Number(e.target.value) })}
          />
          <span className={styles.mono}>{reportConfig.csc_band_low_pct ?? 25}</span>
        </label>
        <label className={styles.field}>
          CSC band high % (percentile)
          <input
            type="range"
            min={10}
            max={95}
            value={reportConfig.csc_band_high_pct ?? 75}
            onChange={(e) => setReportConfig({ csc_band_high_pct: Number(e.target.value) })}
          />
          <span className={styles.mono}>{reportConfig.csc_band_high_pct ?? 75}</span>
        </label>
        <label className={styles.field}>
          Comparable deals from
          <input
            className={styles.textIn}
            type="date"
            value={reportConfig.date_from ?? ''}
            onChange={(e) => setReportConfig({ date_from: e.target.value || undefined })}
          />
        </label>
        <label className={styles.field}>
          Comparable deals to
          <input
            className={styles.textIn}
            type="date"
            value={reportConfig.date_to ?? ''}
            onChange={(e) => setReportConfig({ date_to: e.target.value || undefined })}
          />
        </label>
        <label className={styles.toggle}>
          <input
            type="checkbox"
            checked={reportConfig.verified_only ?? true}
            onChange={(e) => setReportConfig({ verified_only: e.target.checked })}
          />
          Verified-only comparables
        </label>
        <div className={styles.actions}>
          <ActionButton variant="primary" onClick={() => regen()}>
            Generate Report
          </ActionButton>
          <ActionButton variant="secondary" onClick={() => void handleExportPdf()} disabled={pdfLoading}>
            {pdfLoading ? 'Generating PDF…' : 'Export PDF'}
          </ActionButton>
        </div>
      </aside>
    </div>
  )
}

function Section({
  title,
  value,
  onChange,
}: {
  title: string
  value: string
  onChange: (v: string) => void
}) {
  return (
    <div className={styles.section}>
      <div className={styles.sectionTitle}>{title}</div>
      <textarea className={styles.ta} value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  )
}

function ComparablesSection({
  rows,
  onChange,
}: {
  rows: CscReportComparablesRow[] | undefined
  onChange: (rows: CscReportComparablesRow[]) => void
}) {
  const list = rows ?? []
  if (list.length === 0) {
    return (
      <div className={styles.section}>
        <div className={styles.sectionTitle}>Comparables Analysis</div>
        <div className={styles.muted}>No comparables rows in this report.</div>
      </div>
    )
  }
  return (
    <div className={styles.section}>
      <div className={styles.sectionTitle}>Comparables Analysis</div>
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
            {list.map((r) => (
              <tr key={r.athlete_id}>
                <td>
                  <div>{r.name}</div>
                  <div className={styles.subMuted}>
                    {r.school ?? '\u2014'} · {r.position ?? '\u2014'}
                  </div>
                </td>
                <td>{formatScore(r.gravity_score ?? null)}</td>
                <td>{formatScore(r.brand_score ?? null)}</td>
                <td className={styles.amber}>{formatNilMillions(r.nil_valuation_consensus)}</td>
                <td>
                  <input
                    className={styles.cellIn}
                    value={r.deal_structure ?? ''}
                    onChange={(e) => {
                      const next = list.map((x) =>
                        x.athlete_id === r.athlete_id ? { ...x, deal_structure: e.target.value } : x,
                      )
                      onChange(next)
                    }}
                  />
                </td>
                <td>
                  <input
                    className={styles.cellIn}
                    value={r.verified_source ?? ''}
                    onChange={(e) => {
                      const next = list.map((x) =>
                        x.athlete_id === r.athlete_id ? { ...x, verified_source: e.target.value } : x,
                      )
                      onChange(next)
                    }}
                  />
                </td>
                <td>{r.confidence != null ? `${Math.round(r.confidence * 100)}%` : '\u2014'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function NilRangeSection({
  note,
  plotPct,
  low,
  high,
  consensus,
  athleteName,
}: {
  note: string
  plotPct: number
  low: number | null | undefined
  high: number | null | undefined
  consensus: number | null | undefined
  athleteName: string
}) {
  return (
    <div className={styles.section}>
      <div className={styles.sectionTitle}>NIL Range &amp; CSC Band</div>
      <p className={styles.prose}>{note}</p>
      <div className={styles.bandLabels}>
        <span>{formatNilMillions(low)}</span>
        <span>{formatNilMillions(high)}</span>
      </div>
      <div className={styles.bandTrack}>
        <div className={styles.bandMarker} style={{ left: `${plotPct}%` }} title={athleteName} />
      </div>
      <div className={styles.bandConsensus}>
        Consensus {formatNilMillions(consensus)} · {athleteName}
      </div>
    </div>
  )
}
