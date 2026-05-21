import type { AlertRecord } from '../types/alerts'
import type { AthleteRecord, ComparableRecord, ScoreHistoryPoint } from '../types/athlete'
import type { FeedEventRecord } from '../types/feed'
import type {
  AlternativesResponse,
  ConfidenceResponse,
  DealActionResponse,
} from '../types/nilIntelligence'
import type { BrandMatchBrief, BrandMatchResult, CscReportJson, SchoolIndexRow } from '../types/reports'

export const MOCK_USER_ID = '00000000-0000-4000-8000-000000000001'
/** Demo org for CapIQ mocks (align with DB after migration 006). */
export const MOCK_ORG_ID = '00000000-0000-4000-8000-0000000000aa'

export const ARCH_MANNING_ID = 'a1111111-1111-4111-8111-111111111111'

// Primary demo athlete — Arch Manning (Texas, QB, JR)
export const mockAthletePrimary: AthleteRecord = {
  athlete_id: ARCH_MANNING_ID,
  name: 'Arch Manning',
  position: 'QB',
  school: 'Texas',
  conference: 'SEC',
  sport: 'CFB',
  class_year: 'JR',
  jersey_number: '16',
  height: `6'4"`,
  weight: '235lb',
  gravity_score: 91.2,
  gravity_tier: 'ELITE',
  gravity_percentile: 97,
  gravity_delta_30d: 3.4,
  brand_score: 95,
  proof_score: 88,
  proximity_score: 92,
  velocity_score: 84,
  risk_score: 4,
  component_deltas: {
    brand: 2.1,
    proof: 1.4,
    proximity: 0.8,
    velocity: 0.6,
    risk: -0.2,
  },
  nil_valuation_consensus: 4_200_000,
  nil_range_low: 3_600_000,
  nil_range_high: 5_100_000,
  nil_valuation_percentile: 97,
  nil_valuation_delta_30d: 6.8,
  social_combined_reach: 4_800_000,
  instagram_engagement_rate: 7.2,
  news_mentions_30d: 218,
  on3_nil_rank: '#1 CFB',
  verified_deals_count: 11,
  shap_drivers: {
    brand: '3.4M IG · 1.1M TW · Manning brand legacy',
    proof: 'SEC starter · top passer rating 2025',
    proximity: 'Austin DMA · SEC media footprint',
    velocity: 'Deal velocity top 2% nationally',
    risk: 'No off-field flags · strong academic standing',
  },
  company_gravity_score: 84.6,
  brand_gravity_score: 79.2,
  updated_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
}

// High-tier athlete — Jeremiah Smith (Ohio State, WR, SO)
const mockAthleteHigh: AthleteRecord = {
  athlete_id: 'b2222222-2222-4222-8222-222222222222',
  name: 'Jeremiah Smith',
  position: 'WR',
  school: 'Ohio State',
  conference: 'Big Ten',
  sport: 'CFB',
  class_year: 'SO',
  jersey_number: '4',
  height: `6'3"`,
  weight: '215lb',
  gravity_score: 86.7,
  gravity_tier: 'ELITE',
  gravity_percentile: 93,
  gravity_delta_30d: 1.8,
  brand_score: 89,
  proof_score: 87,
  proximity_score: 84,
  velocity_score: 80,
  risk_score: 7,
  nil_valuation_consensus: 2_800_000,
  nil_range_low: 2_400_000,
  nil_range_high: 3_300_000,
  nil_valuation_percentile: 92,
  nil_valuation_delta_30d: 3.1,
  social_combined_reach: 2_100_000,
  instagram_engagement_rate: 5.9,
  news_mentions_30d: 164,
  on3_nil_rank: '#3 CFB',
  verified_deals_count: 8,
  company_gravity_score: 81.3,
  brand_gravity_score: 74.5,
  updated_at: new Date().toISOString(),
}

// Mid breakout — Ryan Williams (Alabama, WR, SO)
const mockAthleteMid: AthleteRecord = {
  athlete_id: 'c3333333-3333-4333-8333-333333333333',
  name: 'Ryan Williams',
  position: 'WR',
  school: 'Alabama',
  conference: 'SEC',
  sport: 'CFB',
  class_year: 'SO',
  jersey_number: '2',
  height: `6'1"`,
  weight: '185lb',
  gravity_score: 74.8,
  gravity_tier: 'BREAKOUT',
  gravity_percentile: 74,
  gravity_delta_30d: 4.2,
  brand_score: 77,
  proof_score: 72,
  proximity_score: 70,
  velocity_score: 82,
  risk_score: 14,
  nil_valuation_consensus: 1_100_000,
  nil_range_low: 880_000,
  nil_range_high: 1_400_000,
  nil_valuation_percentile: 76,
  nil_valuation_delta_30d: 7.4,
  social_combined_reach: 940_000,
  instagram_engagement_rate: 6.1,
  news_mentions_30d: 98,
  on3_nil_rank: '#14 CFB WR',
  verified_deals_count: 4,
  company_gravity_score: 76.9,
  brand_gravity_score: 61.0,
  updated_at: new Date().toISOString(),
}

// Developing — DJ Lagway (Florida, QB, SO)
const mockAthleteLow: AthleteRecord = {
  athlete_id: 'd4444444-4444-4444-8444-444444444444',
  name: 'DJ Lagway',
  position: 'QB',
  school: 'Florida',
  conference: 'SEC',
  sport: 'CFB',
  class_year: 'SO',
  jersey_number: '2',
  height: `6'2"`,
  weight: '222lb',
  gravity_score: 58.1,
  gravity_tier: 'DEVELOPING',
  gravity_percentile: 43,
  gravity_delta_30d: 2.6,
  brand_score: 56,
  proof_score: 60,
  proximity_score: 62,
  velocity_score: 58,
  risk_score: 31,
  nil_valuation_consensus: 340_000,
  nil_range_low: 250_000,
  nil_range_high: 440_000,
  nil_valuation_percentile: 45,
  nil_valuation_delta_30d: 2.1,
  social_combined_reach: 380_000,
  instagram_engagement_rate: 4.2,
  news_mentions_30d: 52,
  on3_nil_rank: '#28 CFB QB',
  verified_deals_count: 2,
  company_gravity_score: 68.4,
  brand_gravity_score: 48.2,
  updated_at: new Date().toISOString(),
}

// Women's basketball — JuJu Watkins (USC, G, JR)
const mockAthleteAmber: AthleteRecord = {
  athlete_id: 'e5555555-5555-4555-8555-555555555555',
  name: 'JuJu Watkins',
  position: 'G',
  school: 'USC',
  conference: 'Big Ten',
  sport: 'NCAAW',
  class_year: 'JR',
  jersey_number: '12',
  height: `6'0"`,
  weight: '165lb',
  gravity_score: 79.6,
  gravity_tier: 'ESTABLISHING',
  gravity_percentile: 81,
  gravity_delta_30d: 1.9,
  brand_score: 84,
  proof_score: 76,
  proximity_score: 78,
  velocity_score: 74,
  risk_score: 16,
  nil_valuation_consensus: 820_000,
  nil_range_low: 680_000,
  nil_range_high: 1_050_000,
  nil_valuation_percentile: 83,
  nil_valuation_delta_30d: 4.8,
  social_combined_reach: 1_600_000,
  instagram_engagement_rate: 8.1,
  news_mentions_30d: 88,
  on3_nil_rank: '#6 NCAAW',
  verified_deals_count: 5,
  company_gravity_score: 71.2,
  brand_gravity_score: 66.8,
  updated_at: new Date().toISOString(),
}

export const mockAthletesById: Record<string, AthleteRecord> = {
  [ARCH_MANNING_ID]: mockAthletePrimary,
  [mockAthleteHigh.athlete_id]: mockAthleteHigh,
  [mockAthleteMid.athlete_id]: mockAthleteMid,
  [mockAthleteLow.athlete_id]: mockAthleteLow,
  [mockAthleteAmber.athlete_id]: mockAthleteAmber,
}

const decisionByAthleteId: Record<
  string,
  {
    recommendation: DealActionResponse['recommendation']
    urgency: DealActionResponse['urgency']
    rangeSpreadPct: number
    walkAwayPremiumPct: number
    structure: DealActionResponse['structure']
    rationale: string[]
    confidenceScore: number
    confidenceLabel: ConfidenceResponse['overall_label']
    caveats: string[]
  }
> = {
  [ARCH_MANNING_ID]: {
    recommendation: 'NEGOTIATE',
    urgency: 'HIGH',
    rangeSpreadPct: 0.16,
    walkAwayPremiumPct: 0.22,
    structure: {
      structure_type: 'hybrid',
      term_months: 12,
      upfront_pct: 70,
      incentive_pct: 30,
      notes: 'Use national media escalators and playoff appearance kicker.',
    },
    rationale: [
      'Elite brand and proof scores support premium market pricing.',
      'Velocity remains elevated with low narrative risk.',
      'Comparables indicate leverage exists below current ask.',
    ],
    confidenceScore: 0.88,
    confidenceLabel: 'HIGH',
    caveats: ['National-tier bidding can move ceiling quickly near season start.'],
  },
  [mockAthleteHigh.athlete_id]: {
    recommendation: 'OFFER_NOW',
    urgency: 'HIGH',
    rangeSpreadPct: 0.14,
    walkAwayPremiumPct: 0.18,
    structure: {
      structure_type: 'hybrid',
      term_months: 10,
      upfront_pct: 75,
      incentive_pct: 25,
      notes: 'Front-load creative deliverables before conference play.',
    },
    rationale: [
      'Strong proof and brand with manageable risk profile.',
      'Price curve steepens when media moments cluster.',
      'Comparable verified deals indicate near-term entry point is favorable.',
    ],
    confidenceScore: 0.83,
    confidenceLabel: 'HIGH',
    caveats: ['Slight concentration in football-only comp set.'],
  },
  [mockAthleteMid.athlete_id]: {
    recommendation: 'OFFER_NOW',
    urgency: 'MEDIUM',
    rangeSpreadPct: 0.18,
    walkAwayPremiumPct: 0.2,
    structure: {
      structure_type: 'performance_heavy',
      term_months: 12,
      upfront_pct: 55,
      incentive_pct: 45,
      notes: 'Tie upside to usage milestones and postseason media windows.',
    },
    rationale: [
      'Velocity breakout creates value before full market repricing.',
      'Brand trend is improving faster than current valuation consensus.',
      'Risk remains below peer-average for breakout tier.',
    ],
    confidenceScore: 0.74,
    confidenceLabel: 'MEDIUM',
    caveats: ['Smaller verified-deal sample than elite-tier peers.'],
  },
  [mockAthleteLow.athlete_id]: {
    recommendation: 'WAIT',
    urgency: 'LOW',
    rangeSpreadPct: 0.2,
    walkAwayPremiumPct: 0.12,
    structure: {
      structure_type: 'performance_heavy',
      term_months: 9,
      upfront_pct: 40,
      incentive_pct: 60,
      notes: 'Use low-guarantee, milestone-driven structure to cap downside.',
    },
    rationale: [
      'Risk profile is elevated relative to current gravity level.',
      'Current market price does not fully discount uncertainty.',
      'Monitoring window likely improves entry terms.',
    ],
    confidenceScore: 0.62,
    confidenceLabel: 'MEDIUM',
    caveats: ['Narrative risk can move rapidly with limited signal depth.'],
  },
  [mockAthleteAmber.athlete_id]: {
    recommendation: 'NEGOTIATE',
    urgency: 'MEDIUM',
    rangeSpreadPct: 0.15,
    walkAwayPremiumPct: 0.17,
    structure: {
      structure_type: 'hybrid',
      term_months: 12,
      upfront_pct: 68,
      incentive_pct: 32,
      notes: 'Prioritize social-content package with tournament bonus ladder.',
    },
    rationale: [
      'Brand efficiency outperforms same-tier peer group.',
      'Engagement metrics support premium partner conversion.',
      'Basketball comp cohort supports upside with controlled downside.',
    ],
    confidenceScore: 0.8,
    confidenceLabel: 'HIGH',
    caveats: ['Cross-sport comparable depth is intentionally excluded from estimate.'],
  },
}

function nilBaseline(athlete: AthleteRecord): number {
  return athlete.nil_valuation_consensus ?? athlete.dollar_p50_usd ?? 250_000
}

function recencyForAthlete(athlete: AthleteRecord) {
  const fallback = new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString()
  return {
    score_last_updated_at: athlete.updated_at ?? fallback,
    data_last_verified_at: athlete.updated_at ?? fallback,
  }
}

export function mockDealAction(athleteId: string): DealActionResponse | null {
  const athlete = mockAthletesById[athleteId]
  const decision = decisionByAthleteId[athleteId]
  if (!athlete || !decision) return null
  const baseline = nilBaseline(athlete)
  const low = Math.round(baseline * (1 - decision.rangeSpreadPct / 2))
  const high = Math.round(baseline * (1 + decision.rangeSpreadPct / 2))
  const walkAway = Math.round(high * (1 + decision.walkAwayPremiumPct))
  return {
    athlete_id: athleteId,
    recommendation: decision.recommendation,
    urgency: decision.urgency,
    recommended_range_low_usd: low,
    recommended_range_high_usd: high,
    walk_away_price_usd: walkAway,
    rationale: decision.rationale,
    structure: decision.structure,
    generated_at: new Date().toISOString(),
  }
}

export function mockConfidence(athleteId: string): ConfidenceResponse | null {
  const athlete = mockAthletesById[athleteId]
  const decision = decisionByAthleteId[athleteId]
  if (!athlete || !decision) return null
  const verifiedDeals = athlete.verified_deals_count ?? 0
  const compCount = athleteId === ARCH_MANNING_ID ? mockComparablesPrimary.length + 1 : 4
  const similarity =
    athleteId === ARCH_MANNING_ID
      ? Number(
          (
            mockComparablesPrimary.reduce((sum, c) => sum + (c.confidence ?? 0), 0) /
            mockComparablesPrimary.length
          ).toFixed(2),
        )
      : 0.79
  return {
    athlete_id: athleteId,
    overall_score: decision.confidenceScore,
    overall_label: decision.confidenceLabel,
    factors: [
      {
        key: 'sample_depth',
        label: 'Sample Depth',
        score: Math.min(0.98, 0.55 + verifiedDeals * 0.04),
        weight: 0.3,
        detail: `${verifiedDeals} verified deals in corpus`,
      },
      {
        key: 'comparables_quality',
        label: 'Comparables Quality',
        score: similarity ?? 0.7,
        weight: 0.35,
        detail: `${compCount} high-similarity athletes in peer set`,
      },
      {
        key: 'signal_freshness',
        label: 'Signal Freshness',
        score: 0.84,
        weight: 0.2,
        detail: 'Score and social feeds refreshed in the last 24h',
      },
      {
        key: 'volatility_risk',
        label: 'Volatility Adjustment',
        score: Math.max(0.4, (athlete.risk_score ?? 75) / 100),
        weight: 0.15,
        detail: `Risk score ${(athlete.risk_score ?? 75).toFixed(1)} supports certainty band`,
      },
    ],
    caveats: decision.caveats,
    freshness: recencyForAthlete(athlete),
    comparables: {
      cohort_size: compCount,
      verified_deals_in_cohort: Math.max(verifiedDeals, compCount),
      median_similarity: similarity,
    },
  }
}

export function mockAlternatives(athleteId: string): AlternativesResponse | null {
  const athlete = mockAthletesById[athleteId]
  if (!athlete) return null
  const subjectNil = nilBaseline(athlete)
  const alternatives = mockWatchlistAthletes
    .filter((a) => a.athlete_id !== athleteId && a.sport === athlete.sport)
    .map((cand) => {
      const candNil = nilBaseline(cand)
      const gravityGap = Math.abs((athlete.gravity_score ?? 0) - (cand.gravity_score ?? 0))
      const riskBonus = Math.max(0, (cand.risk_score ?? 0) - (athlete.risk_score ?? 0))
      const fitScore = Math.max(1, Math.round(100 - gravityGap * 1.2 + riskBonus * 0.6))
      const savings = Math.max(0, Math.round(subjectNil - candNil))
      return {
        athlete_id: cand.athlete_id,
        name: cand.name,
        school: cand.school ?? null,
        position: cand.position ?? null,
        gravity_score: cand.gravity_score ?? null,
        nil_valuation_consensus: candNil,
        risk_score: cand.risk_score ?? null,
        fit_score: fitScore,
        expected_savings_vs_subject_usd: savings > 0 ? savings : null,
        why_better:
          savings > 0
            ? 'Comparable upside at lower expected cost.'
            : 'Higher certainty profile despite similar pricing.',
      }
    })
    .sort((a, b) => b.fit_score - a.fit_score)
    .slice(0, 3)
  return {
    athlete_id: athleteId,
    generated_at: new Date().toISOString(),
    alternatives,
  }
}

export const mockWatchlistAthletes: AthleteRecord[] = [
  mockAthletePrimary,
  mockAthleteHigh,
  mockAthleteMid,
  mockAthleteLow,
  mockAthleteAmber,
]

export const mockComparablesPrimary: ComparableRecord[] = [
  {
    athlete_id: mockAthleteHigh.athlete_id,
    name: 'Jeremiah Smith',
    school: 'Ohio State',
    position: 'WR',
    gravity_score: 86.7,
    brand_score: 89,
    nil_valuation_consensus: 2_800_000,
    nil_delta_vs_subject: -1_400_000,
    confidence: 0.91,
    verified_deal_count: 8,
  },
  {
    athlete_id: mockAthleteMid.athlete_id,
    name: 'Ryan Williams',
    school: 'Alabama',
    position: 'WR',
    gravity_score: 74.8,
    brand_score: 77,
    nil_valuation_consensus: 1_100_000,
    nil_delta_vs_subject: -3_100_000,
    confidence: 0.84,
    verified_deal_count: 4,
  },
  {
    athlete_id: mockAthleteLow.athlete_id,
    name: 'DJ Lagway',
    school: 'Florida',
    position: 'QB',
    gravity_score: 58.1,
    brand_score: 56,
    nil_valuation_consensus: 340_000,
    nil_delta_vs_subject: -3_860_000,
    confidence: 0.76,
    verified_deal_count: 2,
  },
]

export function mockScoreHistory(athleteId: string): ScoreHistoryPoint[] {
  const base = athleteId === ARCH_MANNING_ID ? 88 : 70
  const out: ScoreHistoryPoint[] = []
  for (let i = 30; i >= 0; i--) {
    const d = new Date()
    d.setDate(d.getDate() - i)
    out.push({
      date: d.toISOString().slice(0, 10),
      gravity_score: Math.min(100, Math.max(0, base + (30 - i) * 0.12 + Math.sin(i / 3) * 0.8)),
    })
  }
  return out
}

export const mockFeedPrimary: FeedEventRecord[] = [
  {
    event_id: 'f1',
    athlete_id: ARCH_MANNING_ID,
    athlete_name: 'Arch Manning',
    event_type: 'NIL_DEAL',
    timestamp: new Date(Date.now() - 20 * 60 * 1000).toISOString(),
    body: 'New verified deal with national sports apparel brand confirmed.',
    entity_name: 'Jordan Brand',
    value: 750_000,
  },
  {
    event_id: 'f2',
    athlete_id: ARCH_MANNING_ID,
    event_type: 'BRAND',
    timestamp: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
    body: 'Search volume spike following SEC Spring Game performance.',
    entity_name: 'SEC Media',
    value: null,
  },
  {
    event_id: 'f3',
    athlete_id: ARCH_MANNING_ID,
    event_type: 'VELOCITY',
    timestamp: new Date(Date.now() - 6 * 60 * 60 * 1000).toISOString(),
    body: 'Deal velocity increased 18% week-over-week — highest in CFB QB cohort.',
    entity_name: 'Velocity',
    value: 18.2,
  },
  {
    event_id: 'f4',
    athlete_id: ARCH_MANNING_ID,
    event_type: 'SCORE_UPDATE',
    timestamp: new Date(Date.now() - 22 * 60 * 60 * 1000).toISOString(),
    body: 'Gravity Score revised upward after social reach and deal velocity refresh.',
    entity_name: 'Gravity Score',
    value: 91.2,
  },
  {
    event_id: 'f5',
    athlete_id: ARCH_MANNING_ID,
    event_type: 'RISK',
    timestamp: new Date(Date.now() - 30 * 60 * 60 * 1000).toISOString(),
    body: 'No new risk signals detected. Narrative clean across monitored channels.',
    entity_name: 'Risk Monitor',
    value: null,
  },
]

export const mockAlerts: AlertRecord[] = [
  {
    alert_id: 'al1',
    athlete_id: mockAthleteMid.athlete_id,
    athlete_name: 'Ryan Williams',
    school: 'Alabama',
    alert_type: 'SCORE_MOVE',
    severity: 'INFO',
    description: 'Gravity Score +4.2 after breakout performance — velocity now top 10% SEC WR.',
    numeric_change: 4.2,
    timestamp: new Date(Date.now() - 25 * 60 * 1000).toISOString(),
  },
  {
    alert_id: 'al2',
    athlete_id: ARCH_MANNING_ID,
    athlete_name: 'Arch Manning',
    school: 'Texas',
    alert_type: 'NIL_SIGNAL',
    severity: 'WARN',
    description: 'New NIL signal above $500K threshold detected.',
    numeric_change: 750_000,
    timestamp: new Date(Date.now() - 4 * 60 * 60 * 1000).toISOString(),
  },
  {
    alert_id: 'al3',
    athlete_id: mockAthleteLow.athlete_id,
    athlete_name: 'DJ Lagway',
    school: 'Florida',
    alert_type: 'RISK_FLAG',
    severity: 'CRITICAL',
    description: 'Risk composite crossed monitoring band — narrative flags elevated.',
    numeric_change: 6.8,
    timestamp: new Date(Date.now() - 9 * 60 * 60 * 1000).toISOString(),
  },
  {
    alert_id: 'al4',
    athlete_id: mockAthleteHigh.athlete_id,
    athlete_name: 'Jeremiah Smith',
    school: 'Ohio State',
    alert_type: 'DEAL_DETECTED',
    severity: 'INFO',
    description: 'Verified deal detected in comparables corpus — brand tier elevated.',
    numeric_change: 380_000,
    timestamp: new Date(Date.now() - 15 * 60 * 60 * 1000).toISOString(),
  },
]

export function mockCscReport(athleteId: string): CscReportJson {
  const a = mockAthletesById[athleteId] ?? mockAthletePrimary
  const rows = mockComparablesPrimary.map((c) => ({
    ...c,
    deal_structure: 'Cash + appearances',
    verified_source: 'On3 Pro',
    confidence: c.confidence ?? 0.85,
  }))
  return {
    value: {
      total_benchmark: a.nil_valuation_consensus ?? a.dollar_p50_usd ?? null,
      range_low: a.nil_range_low ?? a.dollar_p10_usd ?? null,
      range_high: a.nil_range_high ?? a.dollar_p90_usd ?? null,
      tier_tag: 'Mid-tier',
      confidence_tag: 'Moderate Confidence',
    },
    explanation: {
      executive_summary: `${a.name} presents a high-conviction NIL profile within ${a.sport ?? 'CFB'} with Gravity ${a.gravity_score?.toFixed(1) ?? '—'} and verified comparables supporting a tight CSC band.`,
      key_value_drivers: [
        { label: 'Brand Strength', signal: 'High', explanation: 'Strong brand score relative to peers.' },
        { label: 'Market Proof', signal: 'Moderate', explanation: 'Limited but relevant verified deal activity.' },
        { label: 'Exposure', signal: 'Moderate', explanation: 'Program and conference visibility supports valuation.' },
        { label: 'Risk', signal: 'Moderate', explanation: 'No critical volatility flags in latest profile.' },
      ],
      driver_takeaway: `${a.name}'s valuation is primarily supported by brand positioning with stable exposure and manageable risk.`,
    },
    validation: {
      market_context: `Market context (${a.conference ?? 'Conference'} ${a.position ?? 'Position'}): range aligns to verified peer set.`,
      comparable_tier: 'Comparable athletes with similar brand/exposure mix.',
      example_comparables: rows.slice(0, 5),
      takeaway: `${a.name}'s benchmark aligns with similarly tiered peers in the current market.`,
      comparable_state: 'sufficient',
      positional_reference_athletes: [],
    },
    confidence_risk: {
      confidence_level: 'Moderate',
      confidence_note: 'Moderate confidence due to available comparables and current model stability.',
      risk_level: 'Moderate',
      risk_note: 'Operational and narrative risk remain within planning tolerance.',
    },
    detail: {
      shap_attribution: 'Primary lift from brand reach and proof-of-performance; no outsized negative drivers.',
      methodology: 'Gravity CSC methodology v1 — comparables-weighted, verified-deal preferred.',
      inputs: 'Inputs include comparables cohort, score components, and verified deal observations.',
    },
    metadata: {
      tier_version: 'tier_v2',
      tier_v1: 'Mid-tier',
      tier_v2: 'Mid-tier',
      cohort_window_days_used: 21,
      season_state: 'in_season',
      cohort_size: 24,
      cohort_fallback_step: 0,
      comparable_state: 'sufficient',
      comparable_sets_computed_at: new Date().toISOString(),
      exposure_formula_version: 'exposure_formula_v1',
      exposure_formula_weights: { proximity_weight: 0.6, velocity_weight: 0.4 },
      rollout_phase: 'phase4',
      low_cohort_data: false,
      athlete_benchmark_percentile_in_cohort: 55,
    },
    executive_summary: `${a.name} presents a high-conviction NIL profile within ${a.sport ?? 'CFB'}.`,
    gravity_score_table: `Brand ${a.brand_score?.toFixed(1) ?? '—'} · Proof ${a.proof_score?.toFixed(1) ?? '—'}`,
    comparables_analysis: rows,
    nil_range_note: 'Consensus range anchored to verified Power 4 QB/skill-position cohort.',
    shap_narrative: 'Primary lift from brand reach and proof-of-performance.',
    risk_assessment: 'Operational and narrative risk well within tolerance for institutional review.',
    methodology: 'Gravity CSC methodology v1 — comparables-weighted, verified-deal preferred.',
  }
}

type BrandMatchPoolRow = BrandMatchResult & {
  conference_key: string
  category_tags: string[]
}

function fromWatchlistAthlete(ath: AthleteRecord, conferenceKey: string, categoryTags: string[]): BrandMatchPoolRow {
  return {
    athlete_id: ath.athlete_id,
    name: ath.name ?? '',
    school: ath.school,
    position: ath.position,
    conference: ath.conference ?? null,
    sport: ath.sport != null ? String(ath.sport) : null,
    class_year: ath.class_year != null ? String(ath.class_year) : null,
    match_score: 70,
    gravity_score: ath.gravity_score,
    brand_score: ath.brand_score,
    deal_range_low: ath.nil_range_low ?? undefined,
    deal_range_high: ath.nil_range_high ?? undefined,
    social_combined_reach: ath.social_combined_reach,
    instagram_engagement_rate: ath.instagram_engagement_rate,
    verified_deals_count: ath.verified_deals_count,
    fit_rationale: 'Mock fit rationale.',
    recommended_structure: 'HYBRID',
    exclusion_flags: [],
    match_breakdown: {
      brand_alignment: 20,
      geography_overlap: 15,
      category_authenticity: 15,
      engagement_quality: 10,
      risk_alignment: 10,
    },
    athlete: ath,
    conference_key: conferenceKey,
    category_tags: categoryTags,
  }
}

const mockBrandMatchPool: BrandMatchPoolRow[] = [
  fromWatchlistAthlete(mockAthletePrimary, 'sec', ['apparel', 'tech', 'finance', 'auto']),
  fromWatchlistAthlete(mockAthleteHigh, 'big ten', ['apparel', 'food/beverage', 'gaming']),
  fromWatchlistAthlete(mockAthleteMid, 'sec', ['apparel', 'gaming']),
  fromWatchlistAthlete(mockAthleteLow, 'sec', ['apparel', 'food/beverage']),
  fromWatchlistAthlete(mockAthleteAmber, 'big ten', ['apparel', 'gaming', 'tech']),
  {
    athlete_id: 'f6666666-6666-4666-8666-666666666666',
    name: 'KJ Marshall',
    school: 'LSU',
    position: 'WR',
    conference: 'SEC',
    sport: 'CFB',
    class_year: 'JR',
    match_score: 77,
    gravity_score: 73.1,
    brand_score: 80.3,
    deal_range_low: 260_000,
    deal_range_high: 380_000,
    social_combined_reach: 720_000,
    instagram_engagement_rate: 6.9,
    verified_deals_count: 3,
    fit_rationale: '',
    recommended_structure: 'HYBRID',
    exclusion_flags: [],
    match_breakdown: {
      brand_alignment: 24,
      geography_overlap: 17,
      category_authenticity: 15,
      engagement_quality: 12,
      risk_alignment: 9,
    },
    conference_key: 'sec',
    category_tags: ['apparel', 'gaming', 'tech'],
  },
  {
    athlete_id: 'f7777777-7777-4777-8777-777777777777',
    name: 'Noah Reed',
    school: 'Kansas State',
    position: 'WR',
    conference: 'Big 12',
    sport: 'CFB',
    class_year: 'SO',
    match_score: 74,
    gravity_score: 69.2,
    brand_score: 71.5,
    deal_range_low: 180_000,
    deal_range_high: 280_000,
    social_combined_reach: 420_000,
    instagram_engagement_rate: 8.1,
    verified_deals_count: 2,
    fit_rationale: '',
    recommended_structure: 'PERFORMANCE_WEIGHTED',
    exclusion_flags: [],
    match_breakdown: {
      brand_alignment: 21,
      geography_overlap: 13,
      category_authenticity: 14,
      engagement_quality: 17,
      risk_alignment: 9,
    },
    conference_key: 'big 12',
    category_tags: ['apparel', 'gaming', 'food/beverage'],
  },
  {
    athlete_id: 'f8888888-8888-4888-8888-888888888888',
    name: 'Marcus Dane',
    school: 'Penn State',
    position: 'RB',
    conference: 'Big Ten',
    sport: 'CFB',
    class_year: 'JR',
    match_score: 72,
    gravity_score: 70.0,
    brand_score: 69.9,
    deal_range_low: 320_000,
    deal_range_high: 460_000,
    social_combined_reach: 1_300_000,
    instagram_engagement_rate: 2.2,
    verified_deals_count: 7,
    fit_rationale: '',
    recommended_structure: 'FIXED',
    exclusion_flags: ['competing brands'],
    match_breakdown: {
      brand_alignment: 20,
      geography_overlap: 14,
      category_authenticity: 14,
      engagement_quality: 10,
      risk_alignment: 14,
    },
    conference_key: 'big ten',
    category_tags: ['apparel', 'finance', 'auto', 'competing brands'],
  },
  {
    athlete_id: 'f9999999-9999-4999-8999-999999999999',
    name: 'Isaiah Cole',
    school: 'USC',
    position: 'QB',
    conference: 'Pac-12',
    sport: 'CFB',
    class_year: 'SR',
    match_score: 78,
    gravity_score: 77.5,
    brand_score: 82.7,
    deal_range_low: 650_000,
    deal_range_high: 920_000,
    social_combined_reach: 2_200_000,
    instagram_engagement_rate: 4.1,
    verified_deals_count: 8,
    fit_rationale: '',
    recommended_structure: 'HYBRID',
    exclusion_flags: [],
    match_breakdown: {
      brand_alignment: 25,
      geography_overlap: 14,
      category_authenticity: 15,
      engagement_quality: 12,
      risk_alignment: 12,
    },
    conference_key: 'pac-12',
    category_tags: ['auto', 'finance', 'tech'],
  },
  {
    athlete_id: 'fa111111-1111-4111-8111-111111111111',
    name: 'Riley Dunn',
    school: 'TCU',
    position: 'QB',
    conference: 'Big 12',
    sport: 'CFB',
    class_year: 'JR',
    match_score: 76,
    gravity_score: 71.8,
    brand_score: 75.4,
    deal_range_low: 270_000,
    deal_range_high: 420_000,
    social_combined_reach: 540_000,
    instagram_engagement_rate: 5.8,
    verified_deals_count: 3,
    fit_rationale: '',
    recommended_structure: 'HYBRID',
    exclusion_flags: [],
    match_breakdown: {
      brand_alignment: 22,
      geography_overlap: 14,
      category_authenticity: 15,
      engagement_quality: 14,
      risk_alignment: 11,
    },
    conference_key: 'big 12',
    category_tags: ['finance', 'tech', 'auto'],
  },
  {
    athlete_id: 'fa222222-2222-4222-8222-222222222222',
    name: 'Evan Price',
    school: 'Florida State',
    position: 'WR',
    conference: 'ACC',
    sport: 'CFB',
    class_year: 'SO',
    match_score: 71,
    gravity_score: 67.4,
    brand_score: 74.0,
    deal_range_low: 190_000,
    deal_range_high: 300_000,
    social_combined_reach: 390_000,
    instagram_engagement_rate: 7.6,
    verified_deals_count: 1,
    fit_rationale: '',
    recommended_structure: 'PERFORMANCE_WEIGHTED',
    exclusion_flags: [],
    match_breakdown: {
      brand_alignment: 21,
      geography_overlap: 13,
      category_authenticity: 13,
      engagement_quality: 15,
      risk_alignment: 9,
    },
    conference_key: 'acc',
    category_tags: ['apparel', 'food/beverage', 'gaming'],
  },
  {
    athlete_id: 'fa333333-3333-4333-8333-333333333333',
    name: 'Trey Holloway',
    school: 'Georgia',
    position: 'TE',
    conference: 'SEC',
    sport: 'CFB',
    class_year: 'SR',
    match_score: 73,
    gravity_score: 68.6,
    brand_score: 72.4,
    deal_range_low: 210_000,
    deal_range_high: 320_000,
    social_combined_reach: 510_000,
    instagram_engagement_rate: 6.3,
    verified_deals_count: 4,
    fit_rationale: '',
    recommended_structure: 'HYBRID',
    exclusion_flags: ['gambling'],
    match_breakdown: {
      brand_alignment: 22,
      geography_overlap: 15,
      category_authenticity: 14,
      engagement_quality: 12,
      risk_alignment: 10,
    },
    conference_key: 'sec',
    category_tags: ['apparel', 'food/beverage', 'gambling'],
  },
  {
    athlete_id: 'fa444444-4444-4444-8444-444444444444',
    name: 'Jalen Ortiz',
    school: 'UCLA',
    position: 'PG',
    conference: 'Pac-12',
    sport: 'NCAAB',
    class_year: 'JR',
    match_score: 79,
    gravity_score: 76.1,
    brand_score: 83.0,
    deal_range_low: 300_000,
    deal_range_high: 470_000,
    social_combined_reach: 860_000,
    instagram_engagement_rate: 7.9,
    verified_deals_count: 4,
    fit_rationale: '',
    recommended_structure: 'HYBRID',
    exclusion_flags: [],
    match_breakdown: {
      brand_alignment: 24,
      geography_overlap: 14,
      category_authenticity: 16,
      engagement_quality: 15,
      risk_alignment: 10,
    },
    conference_key: 'pac-12',
    category_tags: ['apparel', 'fashion', 'gaming', 'tech'],
  },
  {
    athlete_id: 'fa555555-5555-4555-8555-555555555555',
    name: 'Cam Bowers',
    school: 'Baylor',
    position: 'SG',
    conference: 'Big 12',
    sport: 'NCAAB',
    class_year: 'SO',
    match_score: 75,
    gravity_score: 70.7,
    brand_score: 74.8,
    deal_range_low: 220_000,
    deal_range_high: 340_000,
    social_combined_reach: 330_000,
    instagram_engagement_rate: 8.3,
    verified_deals_count: 2,
    fit_rationale: '',
    recommended_structure: 'PERFORMANCE_WEIGHTED',
    exclusion_flags: [],
    match_breakdown: {
      brand_alignment: 22,
      geography_overlap: 13,
      category_authenticity: 15,
      engagement_quality: 15,
      risk_alignment: 10,
    },
    conference_key: 'big 12',
    category_tags: ['gaming', 'apparel', 'food/beverage'],
  },
  {
    athlete_id: 'fa666666-6666-4666-8666-666666666666',
    name: 'Sydney Blake',
    school: 'UConn',
    position: 'G',
    conference: 'Big Ten',
    sport: 'NCAAW',
    class_year: 'JR',
    match_score: 80,
    gravity_score: 78.5,
    brand_score: 84.3,
    deal_range_low: 360_000,
    deal_range_high: 520_000,
    social_combined_reach: 1_100_000,
    instagram_engagement_rate: 9.2,
    verified_deals_count: 5,
    fit_rationale: '',
    recommended_structure: 'HYBRID',
    exclusion_flags: [],
    match_breakdown: {
      brand_alignment: 25,
      geography_overlap: 14,
      category_authenticity: 16,
      engagement_quality: 16,
      risk_alignment: 9,
    },
    conference_key: 'big ten',
    category_tags: ['apparel', 'fashion', 'gaming', 'tech'],
  },
  {
    athlete_id: 'fa777777-7777-4777-8777-777777777777',
    name: 'Alyssa Grant',
    school: 'Tennessee',
    position: 'G',
    conference: 'SEC',
    sport: 'NCAAW',
    class_year: 'SO',
    match_score: 77,
    gravity_score: 72.9,
    brand_score: 79.5,
    deal_range_low: 210_000,
    deal_range_high: 320_000,
    social_combined_reach: 620_000,
    instagram_engagement_rate: 8.8,
    verified_deals_count: 3,
    fit_rationale: '',
    recommended_structure: 'HYBRID',
    exclusion_flags: ['adult content'],
    match_breakdown: {
      brand_alignment: 23,
      geography_overlap: 16,
      category_authenticity: 15,
      engagement_quality: 14,
      risk_alignment: 9,
    },
    conference_key: 'sec',
    category_tags: ['apparel', 'food/beverage', 'adult content'],
  },
]

function norm(s: string) {
  return s.trim().toLowerCase()
}

export function mockBrandMatchResults(brief: BrandMatchBrief): BrandMatchResult[] {
  const geo = new Set((brief.geography ?? []).map(norm))
  const excluded = new Set((brief.excluded_categories ?? []).map(norm))
  const category = norm(brief.category ?? 'other')
  const budgetCap = Number(brief.budget ?? 0) * 1.2

  const rows = mockBrandMatchPool
    .map((row) => {
      const p50 =
        typeof row.deal_range_low === 'number' && typeof row.deal_range_high === 'number'
          ? (row.deal_range_low + row.deal_range_high) / 2
          : 0
      if (p50 > budgetCap) return null
      if ((brief.min_social_reach ?? 0) > 0) {
        if ((row.social_combined_reach ?? 0) < Number(brief.min_social_reach)) return null
      }

      const base = Number(row.brand_score ?? 65) * 0.3 + Number(row.gravity_score ?? 60) * 0.2
      const geoBoost = geo.size > 0 && geo.has('southeast') && row.conference_key === 'sec' ? 7 : 0
      const geoBoost2 = geo.size > 0 && geo.has('midwest') && row.conference_key === 'big ten' ? 7 : 0
      const categoryBoost = row.category_tags.includes(category) ? 8 : 0
      const engagementBoost = brief.prioritize_engagement
        ? Math.min(12, Number(row.instagram_engagement_rate ?? 0))
        : Math.min(6, (Number(row.social_combined_reach ?? 0) / 1_000_000) * 6)
      const penalty =
        brief.deal_density_preference === 'few' && (row.verified_deals_count ?? 0) > 6
          ? 10
          : 0

      const flags = row.category_tags.filter((t) => excluded.has(norm(t)))
      const match = Math.max(50, Math.min(99, Math.round(base + geoBoost + geoBoost2 + categoryBoost + engagementBoost - penalty)))
      return {
        ...row,
        match_score: match,
        fit_rationale:
          `Category fit ${categoryBoost > 0 ? 'strong' : 'moderate'} · ` +
          `geo alignment ${geoBoost + geoBoost2 > 0 ? 'elevated' : 'neutral'} · ` +
          `engagement ${brief.prioritize_engagement ? 'prioritized' : 'balanced'}.`,
        match_breakdown: {
          brand_alignment: Math.round(match * 0.3),
          geography_overlap: Math.round(match * 0.2 + geoBoost / 2 + geoBoost2 / 2),
          category_authenticity: Math.round(match * 0.2 + categoryBoost / 2),
          engagement_quality: Math.round(match * 0.15 + engagementBoost / 2),
          risk_alignment: Math.round(match * 0.15),
        },
        recommended_structure:
          (row.instagram_engagement_rate ?? 0) >= 7.5
            ? 'PERFORMANCE_WEIGHTED'
            : (row.verified_deals_count ?? 0) >= 5
              ? 'FIXED'
              : 'HYBRID',
        exclusion_flags: flags,
      } as BrandMatchResult
    })
    .filter(Boolean) as BrandMatchResult[]

  return rows.sort((a, b) => (b.match_score ?? 0) - (a.match_score ?? 0)).slice(0, 25)
}

export const mockMarketScanAthletes: AthleteRecord[] = mockWatchlistAthletes

export const mockSchoolIndex: SchoolIndexRow[] = [
  {
    team_id: '11111111-1111-4111-8111-111111111111',
    school: 'Texas',
    conference: 'SEC',
    sport: 'cfb',
    avg_gravity_score: 82.1,
    watchlisted_count: 4,
    top_athlete_name: 'Arch Manning',
    nil_market_size_estimate: 58_000_000,
  },
  {
    team_id: '22222222-2222-4222-8222-222222222222',
    school: 'Ohio State',
    conference: 'Big Ten',
    sport: 'cfb',
    avg_gravity_score: 79.4,
    watchlisted_count: 3,
    top_athlete_name: 'Jeremiah Smith',
    nil_market_size_estimate: 44_000_000,
  },
  {
    team_id: null,
    school: 'Alabama',
    conference: 'SEC',
    sport: 'cfb',
    avg_gravity_score: 76.2,
    watchlisted_count: 2,
    top_athlete_name: 'Ryan Williams',
    nil_market_size_estimate: 38_000_000,
  },
]

export function searchMockAthletesByName(q: string): AthleteRecord[] {
  const s = q.trim().toLowerCase()
  if (!s) return Object.values(mockAthletesById)
  return mockWatchlistAthletes.filter((a) => a.name.toLowerCase().includes(s))
}
