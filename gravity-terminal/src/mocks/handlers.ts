import type { BrandMatchBrief, BrandMatchResult } from '../types/reports'
import {
  ARCH_MANNING_ID,
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
    return json({ user_id: MOCK_USER_ID, email: 'demo@gravity.local', role: 'agent' })
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

  if (p.startsWith('athletes?') && method === 'GET') {
    const params = new URLSearchParams(p.slice('athletes?'.length))
    const q = params.get('q') ?? ''
    const hits = searchMockAthletesByName(q).map((a) => ({ athlete_id: a.athlete_id, name: a.name }))
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
    const items = mockAlerts.map((a) => ({
      id: a.alert_id,
      athlete_id: a.athlete_id,
      athlete_name: a.athlete_name,
      delta: a.numeric_change,
      trigger_reason: a.description,
      created_at: a.timestamp,
    }))
    return json({ items, unread: items.length })
  }

  if (p === 'market/scan' && method === 'GET') {
    const athletes = mockMarketScanAthletes.map((a) => ({
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
    return json({ athletes })
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

  return Promise.reject(new Error(`Mock: unhandled ${method} ${path}`))
}

export function mockSearchAthleteNames(q: string) {
  return searchMockAthletesByName(q)
}

export { ARCH_MANNING_ID, MOCK_USER_ID }
