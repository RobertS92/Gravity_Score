import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { postBrandMatch } from '../../api/reports'
import type { BrandMatchBrief, BrandMatchResult } from '../../types/reports'
import { formatNilMillions, formatScore } from '../../lib/formatters'
import { usePreferencesStore } from '../../stores/preferencesStore'
import { useUiStore } from '../../stores/uiStore'
import { useAthleteStore } from '../../stores/athleteStore'
import { ActionButton } from '../shared/ActionButton'
import { BPXVRBreakdown } from '../panels/BPXVRBreakdown'
import styles from './BrandMatchView.module.css'

const CATEGORIES = ['apparel', 'food/beverage', 'tech', 'finance', 'auto', 'gaming', 'other'] as const
const GEO = ['Northeast', 'Southeast', 'Midwest', 'West', 'National'] as const
const AUD = ['18-24', '25-34', 'female-skewing', 'male-skewing', 'multicultural'] as const
const EXCLUSIONS = [
  'alcohol',
  'gambling',
  'firearms',
  'tobacco',
  'competing brands',
  'adult content',
] as const
const REACH_PRESETS = [100_000, 500_000, 1_000_000, 5_000_000] as const

type SortKey =
  | 'match_score'
  | 'brand_score'
  | 'social_combined_reach'
  | 'deal_range_low'
  | 'instagram_engagement_rate'

function fmtReach(n: number | null | undefined) {
  if (n == null || Number.isNaN(n)) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${Math.round(n / 1_000)}K`
  return String(Math.round(n))
}

function dotsForDeals(n: number | null | undefined) {
  if (n == null || n <= 0) return 1
  if (n <= 2) return 2
  if (n <= 4) return 3
  if (n <= 6) return 4
  return 5
}

export function BrandMatchView() {
  const navigate = useNavigate()
  const activeSports = usePreferencesStore((s) => s.activeSports)
  const setSummary = useUiStore((s) => s.setBrandMatchSummary)
  const refineToken = useUiStore((s) => s.brandMatchRefineToken)
  const setResultContext = useUiStore((s) => s.setBrandMatchResultContext)
  const shortlist = useUiStore((s) => s.brandMatchShortlist)
  const toggleShortlist = useUiStore((s) => s.toggleBrandMatchShortlist)
  const briefSummary = useUiStore((s) => s.brandMatchSummary)
  const [budget, setBudget] = useState(400_000)
  const [category, setCategory] = useState<string>('apparel')
  const [geo, setGeo] = useState<string[]>(['Southeast'])
  const [aud, setAud] = useState<string[]>(['18-24'])
  const [riskTol, setRiskTol] = useState(0.5)
  const [maxTransfer, setMaxTransfer] = useState(false)
  const [authW, setAuthW] = useState(0.6)
  const [minSocialReach, setMinSocialReach] = useState<number>(0)
  const [prioritizeEngagement, setPrioritizeEngagement] = useState(false)
  const [excludedCategories, setExcludedCategories] = useState<string[]>([])
  const [dealDensityPreference, setDealDensityPreference] = useState<'few' | 'moderate' | 'any'>('any')
  const [collapsed, setCollapsed] = useState(false)
  const [results, setResults] = useState<BrandMatchResult[] | null>(null)
  const [activeRow, setActiveRow] = useState<string | null>(null)
  const [sortBy, setSortBy] = useState<SortKey>('match_score')
  const [minMatch, setMinMatch] = useState(50)
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
      min_social_reach: minSocialReach > 0 ? minSocialReach : undefined,
      prioritize_engagement: prioritizeEngagement,
      excluded_categories: excludedCategories,
      deal_density_preference: dealDensityPreference,
      sports: activeSports,
    }
    const floor = minSocialReach > 0 ? ` · min ${fmtReach(minSocialReach)} reach` : ''
    setSummary(`$${(budget / 1000).toFixed(0)}K · ${category} · ${geo.join(', ')}${floor}`)
    const r = await postBrandMatch(brief)
    setResults(r)
    setResultContext(r)
    setCollapsed(true)
  }

  const shownResults = useMemo(() => {
    if (!results) return []
    const filtered = results.filter((r) => (r.match_score ?? 0) >= minMatch)
    return [...filtered].sort((a, b) => {
      const av = Number(a[sortBy] ?? 0)
      const bv = Number(b[sortBy] ?? 0)
      return bv - av
    })
  }, [results, sortBy, minMatch])

  useEffect(() => {
    if (!results) return
    setCollapsed(false)
  }, [refineToken, results])

  return (
    <div className={styles.root}>
      {!collapsed ? (
        <div className={styles.form}>
          <div className={styles.formGrid}>
            <div className={styles.col}>
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
                DEAL DENSITY PREFERENCE
                <div className={styles.radioRow}>
                  {[
                    { id: 'few', label: 'FEW DEALS' },
                    { id: 'moderate', label: 'MODERATE' },
                    { id: 'any', label: 'ANY' },
                  ].map((opt) => (
                    <label key={opt.id} className={styles.radioLabel}>
                      <input
                        type="radio"
                        name="deal-density"
                        checked={dealDensityPreference === opt.id}
                        onChange={() => setDealDensityPreference(opt.id as 'few' | 'moderate' | 'any')}
                      />
                      {opt.label}
                    </label>
                  ))}
                </div>
              </div>
              <label className={styles.label}>
                MIN SOCIAL REACH
                <input
                  className={styles.input}
                  type="number"
                  value={minSocialReach}
                  onChange={(e) => setMinSocialReach(Number(e.target.value))}
                />
              </label>
              <div className={styles.chips}>
                {REACH_PRESETS.map((p) => (
                  <button
                    key={p}
                    type="button"
                    className={minSocialReach === p ? styles.chipOn : styles.chip}
                    onClick={() => setMinSocialReach(p)}
                  >
                    {fmtReach(p)}
                  </button>
                ))}
              </div>
            </div>
            <div className={styles.col}>
              <div className={styles.label}>
                GEOGRAPHY
                <div className={styles.chips}>
                  {GEO.map((g) => (
                    <button
                      key={g}
                      type="button"
                      className={geo.includes(g) ? styles.chipOn : styles.chip}
                      onClick={() => setGeo((x) => (x.includes(g) ? x.filter((y) => y !== g) : [...x, g]))}
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
                      onClick={() => setAud((x) => (x.includes(g) ? x.filter((y) => y !== g) : [...x, g]))}
                    >
                      {g}
                    </button>
                  ))}
                </div>
              </div>
              <label className={styles.toggle}>
                <input type="checkbox" checked={prioritizeEngagement} onChange={(e) => setPrioritizeEngagement(e.target.checked)} />
                Prioritize engagement rate over reach
              </label>
              <div className={styles.label}>
                CATEGORY EXCLUSIONS
                <div className={styles.chips}>
                  {EXCLUSIONS.map((x) => (
                    <button
                      key={x}
                      type="button"
                      className={excludedCategories.includes(x) ? styles.chipOn : styles.chip}
                      onClick={() =>
                        setExcludedCategories((arr) =>
                          arr.includes(x) ? arr.filter((v) => v !== x) : [...arr, x],
                        )
                      }
                    >
                      {x}
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
            </div>
          </div>
          <div className={styles.submitBtn}>
            <ActionButton variant="primary" onClick={() => void submit()}>
            FIND MATCHES
            </ActionButton>
          </div>
        </div>
      ) : (
        <div className={styles.summaryLine}>
          <span>
            {briefSummary ?? 'Brief'}
            {results ? ` · ${results.length} matches` : ''}
          </span>
          <button type="button" className={styles.link} onClick={() => setCollapsed(false)}>
            EDIT
          </button>
        </div>
      )}

      {results && (
        <div className={styles.results}>
          <div className={styles.toolbar}>
            <div className={styles.toolbarStats}>{shownResults.length} athletes match your brief</div>
            <label className={styles.toolbarField}>
              SORT
              <select className={styles.input} value={sortBy} onChange={(e) => setSortBy(e.target.value as SortKey)}>
                <option value="match_score">MATCH SCORE</option>
                <option value="brand_score">BRAND SCORE</option>
                <option value="social_combined_reach">SOCIAL REACH</option>
                <option value="deal_range_low">NIL RANGE LOW</option>
                <option value="instagram_engagement_rate">ENGAGEMENT RATE</option>
              </select>
            </label>
            <label className={styles.toolbarField}>
              MIN MATCH {minMatch}
              <input type="range" min={50} max={90} value={minMatch} onChange={(e) => setMinMatch(Number(e.target.value))} />
            </label>
          </div>
          {shownResults.map((r, idx) => (
            <div
              key={r.athlete_id}
              className={`${styles.row} ${activeRow === r.athlete_id ? styles.rowActive : ''}`}
              onMouseEnter={() => setActiveRow(r.athlete_id)}
              onMouseLeave={() => setActiveRow(null)}
              onClick={() => setActiveRow((prev) => (prev === r.athlete_id ? null : r.athlete_id))}
            >
              <div className={styles.rank}>{idx + 1}</div>
              <div className={styles.main}>
                <div className={styles.name}>{r.name}</div>
                <div className={styles.sub}>
                  {[r.school, r.conference, r.position].filter(Boolean).join(' · ')}
                </div>
                {activeRow === r.athlete_id && (
                  <div className={styles.expand}>
                    <div className={styles.breakdown}>
                      {[
                        ['Brand Alignment', r.match_breakdown?.brand_alignment],
                        ['Geography Overlap', r.match_breakdown?.geography_overlap],
                        ['Category Authenticity', r.match_breakdown?.category_authenticity],
                        ['Engagement Quality', r.match_breakdown?.engagement_quality],
                        ['Risk Alignment', r.match_breakdown?.risk_alignment],
                      ].map(([label, val]) => (
                        <div key={label} className={styles.breakRow}>
                          <span>{label}</span>
                          <div className={styles.breakTrack}>
                            <div className={styles.breakFill} style={{ width: `${Math.max(0, Math.min(100, Number(val ?? 0)))}%` }} />
                          </div>
                          <span>{formatScore(Number(val ?? 0))}</span>
                        </div>
                      ))}
                    </div>
                    <div className={styles.rat}>{r.fit_rationale}</div>
                    <div className={styles.sub}>
                      Structure: {r.recommended_structure ?? '—'}
                      {(r.exclusion_flags?.length ?? 0) > 0 ? ` · Flags: ${r.exclusion_flags?.join(', ')}` : ''}
                    </div>
                    <div className={styles.sub}>
                      News 30d: {r.athlete?.news_mentions_30d ?? '—'} · Google: {formatScore(r.athlete?.google_trends_score)} · On3: {r.athlete?.on3_nil_rank ?? '—'}
                    </div>
                    {r.athlete && <BPXVRBreakdown athlete={r.athlete} />}
                  </div>
                )}
              </div>
              <div className={styles.metrics}>
                <div className={styles.matchVal}>MATCH {formatScore(r.match_score)}</div>
                <div>GS {formatScore(r.gravity_score)}</div>
                <div>BR {formatScore(r.brand_score)}</div>
                <div>REACH {fmtReach(r.social_combined_reach)}</div>
                <div>ER {r.instagram_engagement_rate != null ? `${formatScore(r.instagram_engagement_rate)}%` : '—'}</div>
                <div className={styles.deal}>
                  {formatNilMillions(r.deal_range_low)} {'\u2013'} {formatNilMillions(r.deal_range_high)}
                </div>
                <div className={styles.dealDots}>
                  {Array.from({ length: dotsForDeals(r.verified_deals_count) }, (_, i) => (
                    <span key={i} className={styles.dot} />
                  ))}
                </div>
              </div>
              <div className={styles.actions}>
                <ActionButton variant="secondary" onClick={() => toggleShortlist(r)}>
                  {shortlist.some((s) => s.athlete_id === r.athlete_id) ? '★ SHORTLISTED' : '☆ SHORTLIST'}
                </ActionButton>
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
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
