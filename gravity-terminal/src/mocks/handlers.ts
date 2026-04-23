import type { BrandMatchBrief, BrandMatchResult } from '../types/reports'
import {
  ARCH_MANNING_ID,
  MOCK_ORG_ID,
  MOCK_USER_ID,
  mockAlerts,
  mockAthletesById,
  mockBrandMatchResults,
  mockComparablesPrimary,
  mockCscReport,
  mockFeedPrimary,
  mockMarketScanAthletes,
  mockSchoolIndex,
  mockScoreHistory,
  mockWatchlistAthletes,
  searchMockAthletesByName,
} from './fixtures'

type MockUserPrefsState = {
  org_type: string | null
  sport_preferences: string[]
  org_name: string | null
  team_or_athlete_seed: string | null
  default_dashboard_tab: string | null
  athletes_default_sort: string | null
  onboarding_completed_at: string | null
  display_name: string | null
  onboarding_goal: string | null
}

function mockDefaultTabForOrg(org: string | null): string {
  switch (org) {
    case 'school':
      return 'roster'
    case 'nil_collective':
    case 'media_research':
      return 'market'
    case 'law_firm_agent':
      return 'deals'
    default:
      return 'athletes'
  }
}

function mockAthletesSortForOrg(org: string | null): string | null {
  return org === 'insurance_finance' ? 'risk_desc' : 'gravity_desc'
}

/** Mutable prefs for MSW (register clears onboarding; onboarding completes). */
let mockUserPrefs: MockUserPrefsState = {
  org_type: 'school',
  sport_preferences: ['CFB'],
  org_name: null,
  team_or_athlete_seed: null,
  default_dashboard_tab: 'roster',
  athletes_default_sort: null,
  onboarding_completed_at: new Date().toISOString(),
  display_name: 'Demo',
  onboarding_goal: null,
}

function athleteCapSport(athleteId: string): string {
  const ath = mockAthletesById[athleteId]
  if (!ath?.sport) return 'CFB'
  if (ath.sport === 'NCAAW') return 'NCAAW'
  if (ath.sport === 'NCAAB') return 'NCAAB'
  return 'CFB'
}

function json(data: unknown) {
  return Promise.resolve(JSON.parse(JSON.stringify(data)) as unknown)
}

function mockAthleteBundle(id: string) {
  const a = mockAthletesById[id]
  if (!a) return null
  const pts = mockScoreHistory(id)
  const score_history = [...pts]
    .reverse()
    .map((p) => ({
      calculated_at: `${p.date}T12:00:00Z`,
      gravity_score: p.gravity_score,
      brand_score: a.brand_score,
      proof_score: a.proof_score,
      proximity_score: a.proximity_score,
      velocity_score: a.velocity_score,
      risk_score: a.risk_score,
      confidence: 0.85,
    }))
  const comparables =
    id === ARCH_MANNING_ID
      ? mockComparablesPrimary.map((c) => ({
          id: c.athlete_id,
          name: c.name,
          school: c.school,
          position: c.position,
          gravity_score: c.gravity_score,
          brand_score: c.brand_score,
          similarity_score: c.confidence,
        }))
      : []
  return {
    athlete: {
      id: a.athlete_id,
      name: a.name,
      school: a.school,
      conference: a.conference,
      position: a.position,
      sport: a.sport === 'CFB' ? 'cfb' : 'mcbb',
      jersey_number: a.jersey_number,
      updated_at: a.updated_at,
    },
    score_history,
    nil_deals: [],
    comparables,
  }
}

export async function mockRequest(
  method: string,
  path: string,
  body?: unknown,
): Promise<unknown> {
  const p = path.replace(/^\/+/, '')

  if (p === 'auth/me' && method === 'GET') {
    return json({
      user_id: MOCK_USER_ID,
      email: 'demo@gravity.local',
      role: 'admin',
      organization: 'Demo University',
      organization_id: MOCK_ORG_ID,
      organization_slug: 'demo-university',
      coach_sports: ['CFB'],
      org_type: mockUserPrefs.org_type,
      display_name: mockUserPrefs.display_name,
      onboarding_completed_at: mockUserPrefs.onboarding_completed_at,
    })
  }

  if (p === 'auth/login' && method === 'POST') {
    const em = (body as { email?: string })?.email ?? 'demo@gravity.local'
    void em
    return json({
      access_token: 'mock-jwt-token',
      token_type: 'bearer',
      user_id: MOCK_USER_ID,
      email: 'demo@gravity.local',
    })
  }

  if (p === 'auth/register' && method === 'POST') {
    const b = body as { display_name?: string }
    mockUserPrefs = {
      ...mockUserPrefs,
      display_name: b.display_name || 'User',
      onboarding_completed_at: null,
      sport_preferences: ['CFB'],
    }
    return json({
      access_token: 'mock-jwt-token',
      token_type: 'bearer',
      user_id: MOCK_USER_ID,
      email: 'demo@gravity.local',
    })
  }

  if (p === 'auth/onboarding' && method === 'POST') {
    const b = body as {
      org_type?: string
      sport_preferences?: string[]
      org_name?: string | null
      team_or_athlete_seed?: string | null
      onboarding_goal?: string | null
    }
    if (mockUserPrefs.onboarding_completed_at) {
      return Promise.reject(new Error('409 Onboarding already completed'))
    }
    const ot = b.org_type ?? 'school'
    const tab = mockDefaultTabForOrg(ot)
    const sort = mockAthletesSortForOrg(ot)
    mockUserPrefs = {
      ...mockUserPrefs,
      org_type: ot,
      sport_preferences: b.sport_preferences?.length ? [...b.sport_preferences] : ['CFB'],
      org_name: b.org_name ?? null,
      team_or_athlete_seed: b.team_or_athlete_seed ?? null,
      onboarding_goal: b.onboarding_goal ?? null,
      default_dashboard_tab: tab,
      athletes_default_sort: sort,
      onboarding_completed_at: new Date().toISOString(),
    }
    return json({
      user_id: MOCK_USER_ID,
      email: 'demo@gravity.local',
      role: 'admin',
      org_type: mockUserPrefs.org_type,
      sport_preferences: mockUserPrefs.sport_preferences,
      org_name: mockUserPrefs.org_name,
      team_or_athlete_seed: mockUserPrefs.team_or_athlete_seed,
      default_dashboard_tab: mockUserPrefs.default_dashboard_tab,
      athletes_default_sort: mockUserPrefs.athletes_default_sort,
      onboarding_completed_at: mockUserPrefs.onboarding_completed_at,
      display_name: mockUserPrefs.display_name,
      onboarding_goal: mockUserPrefs.onboarding_goal,
    })
  }

  if (p === 'user/preferences' && method === 'GET') {
    return json({ ...mockUserPrefs })
  }

  if (p === 'user/preferences' && method === 'PATCH') {
    const b = (body ?? {}) as Record<string, unknown>
    if (Array.isArray(b.sport_preferences) && b.sport_preferences.length) {
      mockUserPrefs.sport_preferences = b.sport_preferences.map(String)
    }
    if ('org_name' in b) mockUserPrefs.org_name = (b.org_name as string | null) ?? null
    if ('team_or_athlete_seed' in b) {
      mockUserPrefs.team_or_athlete_seed = (b.team_or_athlete_seed as string | null) ?? null
    }
    if (typeof b.default_dashboard_tab === 'string') {
      mockUserPrefs.default_dashboard_tab = b.default_dashboard_tab
    }
    if ('onboarding_goal' in b) mockUserPrefs.onboarding_goal = (b.onboarding_goal as string | null) ?? null
    return json({ ...mockUserPrefs })
  }

  if (p.startsWith('athletes?') && method === 'GET') {
    const params = new URLSearchParams(p.slice('athletes?'.length))
    const q = params.get('q') ?? ''
    const sportsCsv = params.get('sports') ?? ''
    const want = sportsCsv
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    let hits = searchMockAthletesByName(q).map((a) => ({ athlete_id: a.athlete_id, name: a.name }))
    if (want.length) {
      hits = hits.filter((h) => want.includes(athleteCapSport(h.athlete_id)))
    }
    return json({ athletes: hits, total: hits.length, returned: hits.length })
  }

  const mAthletes = p.match(/^athletes\/([^/]+)$/)
  if (mAthletes && method === 'GET') {
    const id = mAthletes[1]
    const bundle = mockAthleteBundle(id)
    if (bundle) return json(bundle)
    return Promise.reject(new Error('Athlete not found'))
  }

  const mComp = p.match(/^athletes\/([^/]+)\/comparables$/)
  if (mComp && method === 'GET') {
    const id = mComp[1]
    const bundle = mockAthleteBundle(id)
    return json({ comparables: bundle?.comparables ?? [] })
  }

  const mFeed = p.match(/^athletes\/([^/]+)\/feed$/)
  if (mFeed && method === 'GET') {
    return json({
      events: mockFeedPrimary.map((e) => ({
        event_id: e.event_id,
        athlete_id: e.athlete_id,
        athlete_name: e.athlete_name,
        event_type: e.event_type,
        timestamp: e.timestamp,
        body: e.body,
        entity_name: e.entity_name,
        value: e.value,
      })),
    })
  }

  const mHist = p.match(/^athletes\/([^/]+)\/score-history$/)
  if (mHist && method === 'GET') {
    const pts = mockScoreHistory(mHist[1])
    const history = [...pts].reverse().map((pt) => ({
      calculated_at: `${pt.date}T12:00:00Z`,
      gravity_score: pt.gravity_score,
    }))
    return json({ history })
  }

  if (p.startsWith('watchlist?') && method === 'GET') {
    return json({
      athletes: mockWatchlistAthletes.map((a) => ({
        athlete_id: a.athlete_id,
        name: a.name,
        school: a.school,
        sport: a.sport === 'CFB' ? 'cfb' : 'mcbb',
        gravity_score: a.gravity_score,
        brand_score: a.brand_score,
        proof_score: a.proof_score,
        proximity_score: a.proximity_score,
        velocity_score: a.velocity_score,
        risk_score: a.risk_score,
      })),
    })
  }

  if (p.startsWith('alerts?') && method === 'GET') {
    const params = new URLSearchParams(p.slice('alerts?'.length))
    const sportsCsv = params.get('sports') ?? ''
    const want = sportsCsv
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    const wlIds = new Set(mockWatchlistAthletes.map((a) => a.athlete_id))
    const filtered = mockAlerts.filter(
      (a) =>
        wlIds.has(a.athlete_id) &&
        (!want.length || want.includes(athleteCapSport(a.athlete_id))),
    )
    const items = filtered.map((a) => ({
      id: a.alert_id,
      athlete_id: a.athlete_id,
      athlete_name: a.athlete_name,
      delta: a.numeric_change,
      trigger_reason: a.description,
      created_at: a.timestamp,
    }))
    return json({ items, unread: items.length })
  }

  if (p.startsWith('market/scan') && method === 'GET') {
    const qIdx = p.indexOf('?')
    const params = qIdx >= 0 ? new URLSearchParams(p.slice(qIdx + 1)) : new URLSearchParams()
    const sportsCsv = params.get('sports') ?? ''
    const want = sportsCsv
      .split(',')
      .map((s) => s.trim())
      .filter(Boolean)
    let list = mockMarketScanAthletes
    if (want.length) {
      list = list.filter((a) => want.includes(athleteCapSport(a.athlete_id)))
    }
    const athletes = list.map((a) => ({
      id: a.athlete_id,
      name: a.name,
      school: a.school,
      conference: a.conference,
      position: a.position,
      sport: a.sport === 'CFB' ? 'cfb' : 'mcbb',
      gravity_score: a.gravity_score,
      brand_score: a.brand_score,
      proof_score: a.proof_score,
      proximity_score: a.proximity_score,
      velocity_score: a.velocity_score,
      risk_score: a.risk_score,
    }))
    return json({ athletes, total: athletes.length, returned: athletes.length })
  }

  if (p === 'market/schools' && method === 'GET') {
    return json({ schools: mockSchoolIndex })
  }

  if (p === 'reports/csc' && method === 'POST') {
    const b = body as { athlete_id?: string }
    return json(mockCscReport(b?.athlete_id ?? ARCH_MANNING_ID))
  }

  if (p === 'reports/brand-match' && method === 'POST') {
    const brief = body as BrandMatchBrief
    void brief
    return json(mockBrandMatchResults() as BrandMatchResult[])
  }

  if (p === 'agent/complete' && method === 'POST') {
    return json({ text: 'Agent proxy not available in mock mode. Use structured commands or enable VITE_USE_MOCKS=false with a live API.' })
  }

  const mCapBudget = p.match(/^cap\/budget\/([^/]+)\/([^/]+)$/)
  if (mCapBudget && method === 'GET') {
    return json({
      org_id: mCapBudget[1],
      sport: mCapBudget[2],
      budgets: [{ id: 'b1', fiscal_year: 2026, total_allocation: 50_000_000_00, notes: null, set_by: null, created_at: null, updated_at: null }],
    })
  }

  const mCapUtil = p.match(/^cap\/utilization\/([^/]+)\/([^/]+)\/(\d+)$/)
  if (mCapUtil && method === 'GET') {
    return json({
      org_id: mCapUtil[1],
      sport: mCapUtil[2],
      fiscal_year: Number(mCapUtil[3]),
      total_allocation_cents: 50_000_000_00,
      committed_cents: 32_000_000_00,
      third_party_cents: 2_000_000_00,
      incentive_exposure_cents: 1_500_000_00,
      utilization_pct: 64.0,
      remaining_cents: 18_000_000_00,
    })
  }

  const mCapContracts = p.match(/^cap\/contracts\/([^/]+)\/([^/]+)$/)
  if (mCapContracts && method === 'GET') {
    return json({
      contracts: [
        {
          id: 'c1',
          athlete_id: ARCH_MANNING_ID,
          athlete_name: 'Arch Manning',
          sport: mCapContracts[2],
          base_comp: 4_000_000_00,
          incentives: [],
          third_party_flag: false,
          payment_schedule: {},
          fiscal_year_start: 2026,
          eligibility_years_remaining: 4,
          status: 'active',
          scenario_id: null,
        },
      ],
    })
  }

  const mCapScenList = p.match(/^cap\/org\/([^/]+)\/scenarios\/([^/]+)$/)
  if (mCapScenList && method === 'GET') {
    return json({
      scenarios: [
        {
          id: 's1',
          name: 'Portal push',
          status: 'draft',
          aggregate_gravity_score: 74.2,
          total_committed: 45_000_000_00,
          total_risk_exposure: 2_000_000_00,
          created_at: '2026-04-01T12:00:00Z',
          updated_at: '2026-04-20T12:00:00Z',
          promoted_at: null,
        },
      ],
    })
  }

  const mCapCompare = p.match(/^cap\/scenarios\/([^/]+)\/compare$/)
  if (mCapCompare && method === 'GET') {
    return json({
      official: {
        athletes: [],
        aggregate_gravity: 71.4,
        total_committed_cents: 42_000_000_00,
        avg_risk_score: 28.1,
      },
      scenario: {
        athletes: [],
        aggregate_gravity: 74.8,
        total_committed_cents: 51_000_000_00,
        avg_risk_score: 31.6,
      },
      delta: {
        gravity: 3.4,
        cost_cents: 9_000_000_00,
        risk: 3.5,
        gravity_per_dollar: 'official: mock; scenario: mock',
      },
    })
  }

  const mCapOutlook = p.match(/^cap\/outlook\/([^/]+)\/([^/]+)$/)
  if (mCapOutlook && method === 'GET') {
    const y = new Date().getFullYear()
    return json({
      org_id: mCapOutlook[1],
      sport: mCapOutlook[2],
      years: Array.from({ length: 5 }, (_, i) => ({
        fiscal_year: y + i,
        committed_cents: 30_000_000_00 + i * 1_000_000_00,
        incentive_exposure_cents: 1_000_000_00,
        headcount: 85,
        available_cap_cents: 15_000_000_00,
      })),
    })
  }

  const mCapRollup = p.match(/^cap\/rollup\/([^/]+)$/)
  if (mCapRollup && method === 'GET') {
    return json({
      org_id: mCapRollup[1],
      sports: [
        { sport: 'CFB', fiscal_year: 2026, committed_cents: 32_000_000_00, total_allocation_cents: 50_000_000_00, utilization_pct: 64 },
        { sport: 'NCAAB', fiscal_year: null, utilization_pct: null, committed_cents: 0 },
        { sport: 'NCAAW', fiscal_year: null, utilization_pct: null, committed_cents: 0 },
      ],
    })
  }

  if (p.startsWith('data/submissions/') && method === 'GET') {
    return json({ submissions: [] })
  }

  if (p === 'data/submit' && method === 'POST') {
    return json({ id: 'sub1', status: 'pending', verification_results: null })
  }

  if (p === 'cap/scenarios' && method === 'POST') {
    return json({ id: 's-new', ok: true })
  }

  const mCapScenDetail = p.match(/^cap\/scenarios\/([^/]+)$/)
  if (mCapScenDetail && method === 'GET') {
    return json({
      scenario: {
        id: mCapScenDetail[1],
        org_id: MOCK_ORG_ID,
        sport: 'CFB',
        name: 'Demo scenario',
        status: 'draft',
        aggregate_gravity_score: 74.0,
        total_committed: 45_000_000_00,
        total_risk_exposure: 2_000_000_00,
      },
      contracts: [],
    })
  }

  if (p === 'cap/budget' && method === 'POST') {
    return json({ id: 'b-new', ok: true })
  }

  if (p.startsWith('scraper/') && (method === 'GET' || method === 'POST')) {
    if (p.endsWith('/jobs/queue/status')) return json({ depth_by_priority: { P0: 0, P1: 0, P2: 1, P3: 0, P4: 0 } })
    if (p.endsWith('/jobs/circuits')) return json({ circuits: [] })
    if (p.includes('/jobs/circuits/') && p.endsWith('/reset')) return json({ ok: true, source: 'espn' })
    if (p.includes('/jobs/delta-report/')) return json({ date: '2026-04-01', athletes_changed: null, note: 'mock' })
    if (p.includes('/jobs/athlete/')) return json({ ok: true, queued: true, priority: 'P2' })
    if (p.endsWith('/jobs/event')) return json({ ok: true, priority: 'P2' })
  }

  if (method === 'PATCH' && p.startsWith('cap/')) {
    return json({ ok: true })
  }

  if (p === 'operations/dashboard' && method === 'GET') {
    return json({
      generated_at: new Date().toISOString(),
      database: {
        athletes_total: 1200,
        athletes_with_scores: 800,
        athletes_scraped_7d: 120,
        athletes_last_scraped_set: 900,
        avg_data_quality_score: '0.72',
        athletes_with_dqs: 850,
        raw_athlete_data_rows: 900,
        roster_snapshots_rows: 5000,
        scraper_jobs_in_db: true,
        scraper_jobs_recent: [
          {
            job_type: 'daily_vip_update',
            status: 'completed',
            processed_count: 180,
            failed_count: 2,
            started_at: '2026-04-21T12:00:00.000Z',
          },
          {
            job_type: 'roster_sync',
            status: 'completed',
            processed_count: 200,
            failed_count: 0,
            started_at: '2026-04-21T10:00:00.000Z',
          },
        ],
      },
      scrapers: {
        health: { status: 'healthy', service: 'gravity-scrapers' },
        jobs_progress: { running: false, last_job: null },
      },
      scrapers_error: null,
    })
  }

  return Promise.reject(new Error(`Mock: unhandled ${method} ${path}`))
}

export function mockSearchAthleteNames(q: string) {
  return searchMockAthletesByName(q)
}

export { ARCH_MANNING_ID, MOCK_ORG_ID, MOCK_USER_ID }
