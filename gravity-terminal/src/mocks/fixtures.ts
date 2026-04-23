import type { AlertRecord } from '../types/alerts'
import type { AthleteRecord, ComparableRecord, ScoreHistoryPoint } from '../types/athlete'
import type { FeedEventRecord } from '../types/feed'
import type { BrandMatchResult, CscReportJson, SchoolIndexRow } from '../types/reports'

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
  return {
    executive_summary: `${a.name} presents a high-conviction NIL profile within ${a.sport ?? 'CFB'} with Gravity ${a.gravity_score?.toFixed(1) ?? '—'} and verified comparables supporting a tight CSC band.`,
    gravity_score_table: `Brand ${a.brand_score?.toFixed(1) ?? '—'} · Proof ${a.proof_score?.toFixed(1) ?? '—'} · Proximity ${a.proximity_score?.toFixed(1) ?? '—'} · Velocity ${a.velocity_score?.toFixed(1) ?? '—'} · Risk ${a.risk_score?.toFixed(1) ?? '—'}`,
    comparables_analysis: mockComparablesPrimary.map((c) => ({
      ...c,
      deal_structure: 'Cash + appearances',
      verified_source: 'On3 Pro',
      confidence: c.confidence ?? 0.85,
    })),
    nil_range_note: 'Consensus range anchored to verified Power 4 QB/skill-position cohort.',
    shap_narrative: 'Primary lift from brand reach (Manning legacy amplifier) and proof-of-performance; risk remains minimal.',
    risk_assessment: 'Operational and narrative risk well within tolerance for institutional review.',
    methodology: 'Gravity CSC methodology v1 — comparables-weighted, verified-deal preferred.',
  }
}

export function mockBrandMatchResults(): BrandMatchResult[] {
  return mockWatchlistAthletes.map((ath, i) => ({
    athlete_id: ath.athlete_id,
    name: ath.name ?? '',
    school: ath.school,
    position: ath.position,
    match_score: 94 - i * 7,
    gravity_score: ath.gravity_score,
    brand_score: ath.brand_score,
    deal_range_low: ath.nil_range_low ?? undefined,
    deal_range_high: ath.nil_range_high ?? undefined,
    fit_rationale: `Strong audience overlap with selected geography. Brand dimension aligns with category authenticity weighting.`,
    athlete: ath,
  })).sort((a, b) => b.match_score - a.match_score)
}

export const mockMarketScanAthletes: AthleteRecord[] = mockWatchlistAthletes

export const mockSchoolIndex: SchoolIndexRow[] = [
  {
    school: 'Texas',
    conference: 'SEC',
    avg_gravity_score: 82.1,
    watchlisted_count: 4,
    top_athlete_name: 'Arch Manning',
    nil_market_size_estimate: 58_000_000,
  },
  {
    school: 'Ohio State',
    conference: 'Big Ten',
    avg_gravity_score: 79.4,
    watchlisted_count: 3,
    top_athlete_name: 'Jeremiah Smith',
    nil_market_size_estimate: 44_000_000,
  },
  {
    school: 'Alabama',
    conference: 'SEC',
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
