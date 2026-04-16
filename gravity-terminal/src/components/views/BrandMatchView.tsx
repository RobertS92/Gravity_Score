import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { postBrandMatch } from '../../api/reports'
import type { BrandMatchBrief, BrandMatchResult } from '../../types/reports'
import { formatNilMillions, formatScore } from '../../lib/formatters'
import { useUiStore } from '../../stores/uiStore'
import { useAthleteStore } from '../../stores/athleteStore'
import { ActionButton } from '../shared/ActionButton'
import { BPXVRBreakdown } from '../panels/BPXVRBreakdown'
import styles from './BrandMatchView.module.css'

const CATEGORIES = ['apparel', 'food/beverage', 'tech', 'finance', 'auto', 'gaming', 'other'] as const
const GEO = ['Northeast', 'Southeast', 'Midwest', 'West', 'National'] as const
const AUD = ['18-24', '25-34', 'female-skewing', 'male-skewing', 'multicultural'] as const

export function BrandMatchView() {
  const navigate = useNavigate()
  const setSummary = useUiStore((s) => s.setBrandMatchSummary)
  const briefSummary = useUiStore((s) => s.brandMatchSummary)
  const [budget, setBudget] = useState(400_000)
  const [category, setCategory] = useState<string>('apparel')
  const [geo, setGeo] = useState<string[]>(['Southeast'])
  const [aud, setAud] = useState<string[]>(['18-24'])
  const [riskTol, setRiskTol] = useState(0.5)
  const [maxTransfer, setMaxTransfer] = useState(false)
  const [authW, setAuthW] = useState(0.6)
  const [collapsed, setCollapsed] = useState(false)
  const [results, setResults] = useState<BrandMatchResult[] | null>(null)
  const [activeRow, setActiveRow] = useState<string | null>(null)
  const setActive = useAthleteStore((s) => s.setActiveAthlete)

  const submit = async () => {
    const brief: BrandMatchBrief = {
      budget,
      category,
      geography: geo,
      audience: aud,
      risk_tolerance: riskTol,
      max_transfer_risk: maxTransfer,
      authenticity_weight: authW,
    }
    setSummary(`$${(budget / 1000).toFixed(0)}K · ${category} · ${geo.join(', ')}`)
    const r = await postBrandMatch(brief)
    setResults(r)
    setCollapsed(true)
  }

  return (
    <div className={styles.root}>
      {!collapsed ? (
        <div className={styles.form}>
          <label className={styles.label}>
            BUDGET ($)
            <input
              className={styles.input}
              type="number"
              value={budget}
              onChange={(e) => setBudget(Number(e.target.value))}
            />
          </label>
          <label className={styles.label}>
            CATEGORY
            <select className={styles.input} value={category} onChange={(e) => setCategory(e.target.value)}>
              {CATEGORIES.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          </label>
          <div className={styles.label}>
            GEOGRAPHY
            <div className={styles.chips}>
              {GEO.map((g) => (
                <button
                  key={g}
                  type="button"
                  className={geo.includes(g) ? styles.chipOn : styles.chip}
                  onClick={() =>
                    setGeo((x) => (x.includes(g) ? x.filter((y) => y !== g) : [...x, g]))
                  }
                >
                  {g}
                </button>
              ))}
            </div>
          </div>
          <div className={styles.label}>
            AUDIENCE
            <div className={styles.chips}>
              {AUD.map((g) => (
                <button
                  key={g}
                  type="button"
                  className={aud.includes(g) ? styles.chipOn : styles.chip}
                  onClick={() =>
                    setAud((x) => (x.includes(g) ? x.filter((y) => y !== g) : [...x, g]))
                  }
                >
                  {g}
                </button>
              ))}
            </div>
          </div>
          <label className={styles.label}>
            RISK TOLERANCE
            <input type="range" min={0} max={100} value={Math.round(riskTol * 100)} onChange={(e) => setRiskTol(Number(e.target.value) / 100)} />
          </label>
          <label className={styles.toggle}>
            <input type="checkbox" checked={maxTransfer} onChange={(e) => setMaxTransfer(e.target.checked)} />
            Max transfer risk
          </label>
          <label className={styles.label}>
            AUTHENTICITY WEIGHT
            <input type="range" min={0} max={100} value={Math.round(authW * 100)} onChange={(e) => setAuthW(Number(e.target.value) / 100)} />
          </label>
          <ActionButton variant="primary" onClick={() => void submit()}>
            FIND MATCHES
          </ActionButton>
        </div>
      ) : (
        <div className={styles.summaryLine}>
          <span>{briefSummary ?? 'Brief'}</span>
          <button type="button" className={styles.link} onClick={() => setCollapsed(false)}>
            EDIT
          </button>
        </div>
      )}

      {results && (
        <div className={styles.results}>
          {results.map((r, idx) => (
            <div
              key={r.athlete_id}
              className={`${styles.row} ${activeRow === r.athlete_id ? styles.rowActive : ''}`}
              onMouseEnter={() => setActiveRow(r.athlete_id)}
              onMouseLeave={() => setActiveRow(null)}
            >
              <div className={styles.rank}>{idx + 1}</div>
              <div className={styles.main}>
                <div className={styles.name}>{r.name}</div>
                <div className={styles.sub}>
                  {[r.school, r.position].filter(Boolean).join(' · ')} · MATCH {formatScore(r.match_score)}
                </div>
                {activeRow === r.athlete_id && r.athlete && (
                  <div className={styles.expand}>
                    <BPXVRBreakdown athlete={r.athlete} />
                    <div className={styles.rat}>{r.fit_rationale}</div>
                  </div>
                )}
              </div>
              <div className={styles.metrics}>
                <div>GS {formatScore(r.gravity_score)}</div>
                <div>BR {formatScore(r.brand_score)}</div>
                <div className={styles.deal}>
                  {formatNilMillions(r.deal_range_low)} {'\u2013'} {formatNilMillions(r.deal_range_high)}
                </div>
              </div>
              <ActionButton
                variant="secondary"
                onClick={() => {
                  void setActive(r.athlete_id)
                  navigate('/')
                }}
              >
                Assess Deal
              </ActionButton>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
