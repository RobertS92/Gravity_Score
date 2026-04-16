import { describe, expect, it } from 'vitest'
import { mapAthleteFromBundle, mapFeedEvents, mapScoreHistoryFromApi } from './athlete'

describe('athlete adapters', () => {
  it('maps athlete detail bundle', () => {
    const rec = mapAthleteFromBundle({
      athlete: {
        id: 'a1',
        name: 'Test Athlete',
        school: 'State U',
        conference: 'SEC',
        position: 'QB',
        sport: 'cfb',
      },
      score_history: [
        {
          calculated_at: '2025-01-15T00:00:00Z',
          gravity_score: 80,
          brand_score: 70,
          proof_score: 65,
          proximity_score: 60,
          velocity_score: 55,
          risk_score: 20,
        },
        {
          calculated_at: '2025-01-01T00:00:00Z',
          gravity_score: 78,
          brand_score: 68,
          proof_score: 64,
          proximity_score: 59,
          velocity_score: 54,
          risk_score: 22,
        },
      ],
      nil_deals: [{ deal_value: 100000, verified: true }],
    })
    expect(rec.athlete_id).toBe('a1')
    expect(rec.gravity_score).toBe(80)
    expect(rec.gravity_delta_30d).toBeCloseTo(2, 5)
    expect(rec.nil_valuation_consensus).toBe(100000)
  })

  it('maps score history', () => {
    const pts = mapScoreHistoryFromApi([
      { calculated_at: '2025-01-02T00:00:00Z', gravity_score: 81 },
      { calculated_at: '2025-01-01T00:00:00Z', gravity_score: 80 },
    ])
    expect(pts).toHaveLength(2)
    expect(pts[0].date.startsWith('2025-01-01')).toBe(true)
    expect(pts[0].gravity_score).toBe(80)
  })

  it('maps feed events', () => {
    const ev = mapFeedEvents([
      {
        event_id: 'e1',
        athlete_id: 'a1',
        event_type: 'NIL_DEAL',
        timestamp: '2025-01-01T00:00:00Z',
        body: 'Deal',
      },
    ])
    expect(ev).toHaveLength(1)
    expect(ev[0].event_type).toBe('NIL_DEAL')
  })
})
