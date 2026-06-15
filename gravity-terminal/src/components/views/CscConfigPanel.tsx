import { useMemo } from 'react'
import {
  MARKET_VIEW_OPTIONS,
  REPORT_FOCUS_OPTIONS,
  resolveCscReportParams,
} from '../../lib/cscConfigPresets'
import type { AthleteRecord } from '../../types/athlete'
import { useAthleteStore } from '../../stores/athleteStore'
import { useUiStore } from '../../stores/uiStore'
import { ActionButton } from '../shared/ActionButton'
import styles from './CscReportsView.module.css'


type CscConfigPanelProps = {
  searchQ: string
  setSearchQ: (q: string) => void
  searchOpen: boolean
  setSearchOpen: (open: boolean) => void
  searchLoading: boolean
  searchRows: AthleteRecord[]
  selectorAthletes: AthleteRecord[]
  onSelectAthlete: (id: string) => void
  onRegen: () => void
  onExportPdf: () => void
  pdfLoading: boolean
  hasReport: boolean
}

export function CscConfigPanel({
  searchQ,
  setSearchQ,
  searchOpen,
  setSearchOpen,
  searchLoading,
  searchRows,
  selectorAthletes,
  onSelectAthlete,
  onRegen,
  onExportPdf,
  pdfLoading,
  hasReport,
}: CscConfigPanelProps) {
  const athlete = useAthleteStore((s) => s.activeAthlete)
  const reportConfig = useUiStore((s) => s.reportConfig)
  const setReportConfig = useUiStore((s) => s.setReportConfig)
  const configMode = useUiStore((s) => s.cscConfigMode)
  const setConfigMode = useUiStore((s) => s.setCscConfigMode)
  const simpleConfig = useUiStore((s) => s.cscSimpleConfig)
  const setSimpleConfig = useUiStore((s) => s.setCscSimpleConfig)

  const marketViewHint = useMemo(
    () => MARKET_VIEW_OPTIONS.find((o) => o.value === simpleConfig.marketView)?.hint ?? '',
    [simpleConfig.marketView],
  )

  return (
    <>
      <div className={styles.configModeRow}>
        <button
          type="button"
          className={configMode === 'simple' ? styles.configModeOn : styles.configModeBtn}
          onClick={() => setConfigMode('simple')}
        >
          Simple
        </button>
        <button
          type="button"
          className={configMode === 'advanced' ? styles.configModeOn : styles.configModeBtn}
          onClick={() => setConfigMode('advanced')}
        >
          Analyst
        </button>
      </div>

      <label className={styles.field}>
        Athlete Search
        <input
          autoFocus={!athlete}
          className={styles.textIn}
          type="text"
          placeholder="Search athlete by name..."
          value={searchQ}
          onChange={(e) => setSearchQ(e.target.value)}
          onFocus={() => {
            if (searchRows.length > 0 || searchQ.trim()) setSearchOpen(true)
          }}
        />
      </label>
      {searchOpen && (
        <div className={styles.searchDrop}>
          {searchLoading && <div className={styles.searchItemMuted}>Searching...</div>}
          {!searchLoading && searchRows.length === 0 && (
            <div className={styles.searchItemMuted}>No athletes found</div>
          )}
          {!searchLoading &&
            searchRows.map((a) => (
              <button
                key={a.athlete_id}
                type="button"
                className={styles.searchItem}
                onClick={() => onSelectAthlete(a.athlete_id)}
              >
                <span>{a.name}</span>
                <span className={styles.subMuted}>
                  {[a.school, a.position, a.conference].filter(Boolean).join(' · ')}
                </span>
              </button>
            ))}
        </div>
      )}

      <label className={styles.field}>
        Athlete
        <select
          className={styles.select}
          value={athlete?.athlete_id ?? ''}
          onChange={(e) => {
            if (e.target.value) onSelectAthlete(e.target.value)
          }}
        >
          {!athlete && <option value="">Select athlete…</option>}
          {selectorAthletes.map((a) => (
            <option key={a.athlete_id} value={a.athlete_id}>
              {a.name}
              {a.school ? ` · ${a.school}` : ''}
            </option>
          ))}
        </select>
      </label>

      {configMode === 'simple' ? (
        <>
          <label className={styles.field}>
            Market View
            <select
              className={styles.select}
              value={simpleConfig.marketView}
              onChange={(e) =>
                setSimpleConfig({ marketView: e.target.value as typeof simpleConfig.marketView })
              }
            >
              {MARKET_VIEW_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            <span className={styles.configHint}>{marketViewHint}</span>
          </label>
          <label className={styles.field}>
            Report Focus
            <select
              className={styles.select}
              value={simpleConfig.reportFocus}
              onChange={(e) =>
                setSimpleConfig({ reportFocus: e.target.value as typeof simpleConfig.reportFocus })
              }
            >
              {REPORT_FOCUS_OPTIONS.map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
          <label className={styles.toggle}>
            <input
              type="checkbox"
              checked={simpleConfig.verifiedOnly}
              onChange={(e) => setSimpleConfig({ verifiedOnly: e.target.checked })}
            />
            Verified comparables
          </label>
        </>
      ) : (
        <>
          {/* Sport override removed: the global TopBar chips + the active
              athlete's stored sport already cover this. Surface a read-only
              hint instead so analysts can see which sport will be used. */}
          <div className={styles.field}>
            <div className={styles.configHint}>
              Sport: <strong>{athlete?.sport ?? 'auto'}</strong>{' '}
              <span style={{ color: 'var(--text-dim)' }}>(set on athlete record)</span>
            </div>
          </div>
          <label className={styles.field}>
            Position group (filter)
            <input
              className={styles.textIn}
              type="text"
              placeholder="e.g. WR / QB / EDGE"
              value={reportConfig.position_group ?? reportConfig.position ?? ''}
              onChange={(e) =>
                setReportConfig({
                  position_group: e.target.value || undefined,
                  position: e.target.value || undefined,
                })
              }
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

          <WeightingControls />
        </>
      )}

      <div className={styles.actions}>
        <ActionButton variant="primary" onClick={() => onRegen()} disabled={!athlete}>
          Generate Report
        </ActionButton>
        <ActionButton
          variant="secondary"
          onClick={() => onExportPdf()}
          disabled={pdfLoading || !athlete || !hasReport}
        >
          {pdfLoading ? 'Generating PDF…' : 'Export PDF'}
        </ActionButton>
      </div>
    </>
  )
}

export function useCscResolvedParams() {
  const reportConfig = useUiStore((s) => s.reportConfig)
  const configMode = useUiStore((s) => s.cscConfigMode)
  const simpleConfig = useUiStore((s) => s.cscSimpleConfig)
  const athlete = useAthleteStore((s) => s.activeAthlete)
  return useMemo(
    () => resolveCscReportParams(configMode, simpleConfig, reportConfig, athlete?.sport),
    [configMode, simpleConfig, reportConfig, athlete?.sport],
  )
}

// ---------------------------------------------------------------------------
// Analyst weighting controls
// ---------------------------------------------------------------------------
//
// Lets analysts override the heuristic-fallback weight vector that powers the
// composite score when the production GravityNet model is unavailable.
//
// Weights are enforced to sum to 1: editing one slider redistributes the
// remaining budget proportionally across the others. Default vector matches
// `gravity_api/services/athlete_score_sync.py` lines 237-243.

const DEFAULT_WEIGHTS = {
  brand: 0.28,
  proof: 0.24,
  exposure: 0.18,
  velocity: 0.2,
  risk: 0.1,
}

type WeightKey = keyof typeof DEFAULT_WEIGHTS

function WeightingControls() {
  const reportConfig = useUiStore((s) => s.reportConfig)
  const setReportConfig = useUiStore((s) => s.setReportConfig)
  const current = reportConfig.weighting_override ?? DEFAULT_WEIGHTS

  const updateWeight = (key: WeightKey, nextValue: number) => {
    const clamped = Math.max(0, Math.min(1, nextValue))
    const others = (Object.keys(DEFAULT_WEIGHTS) as WeightKey[]).filter((k) => k !== key)
    const remaining = 1 - clamped
    const othersSum = others.reduce((sum, k) => sum + current[k], 0)
    const next: Record<WeightKey, number> = { ...current, [key]: clamped }
    if (othersSum > 0 && remaining >= 0) {
      // Proportionally rescale the other weights so the total stays exactly 1.
      for (const k of others) {
        next[k] = (current[k] / othersSum) * remaining
      }
    } else if (othersSum === 0 && remaining > 0) {
      // All other weights are zero; distribute remaining evenly.
      const share = remaining / others.length
      for (const k of others) next[k] = share
    }
    setReportConfig({ weighting_override: next })
  }

  const resetWeights = () => setReportConfig({ weighting_override: { ...DEFAULT_WEIGHTS } })

  const total = (Object.keys(current) as WeightKey[]).reduce((s, k) => s + current[k], 0)
  return (
    <div className={styles.weightingSection}>
      <div className={styles.weightingHeader}>
        <span>Weighting Logic (fallback model)</span>
        <button type="button" className={styles.weightingReset} onClick={resetWeights}>
          reset
        </button>
      </div>
      {(Object.keys(DEFAULT_WEIGHTS) as WeightKey[]).map((key) => (
        <label key={key} className={styles.field}>
          <span style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ textTransform: 'capitalize' }}>{key}</span>
            <span className={styles.mono}>{(current[key] * 100).toFixed(0)}%</span>
          </span>
          <input
            type="range"
            min={0}
            max={100}
            step={1}
            value={Math.round(current[key] * 100)}
            onChange={(e) => updateWeight(key, Number(e.target.value) / 100)}
          />
        </label>
      ))}
      <div className={styles.configHint} style={{ marginTop: 4 }}>
        Total: {(total * 100).toFixed(0)}% — applied only on fallback-model scores.
      </div>
    </div>
  )
}
