import { describe, expect, it } from 'vitest'
import {
  mapAthleteFromBundle,
  mapComparableRow,
  mapComparablesFromBundle,
  mapFeedEvents,
  mapScoreHistoryFromApi,
  mapSearchRowToAthlete,
  mapWatchlistAthleteRow,
} from './athlete'

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

  it('maps NBA Impact aliases from detail and search payloads', () => {
    const detail = mapAthleteFromBundle({
      athlete: {
        id: 'nba1',
        name: 'NBA Star',
        sport: 'nba',
        impact_score: 88.4,
        impact_sport_percentile: 97,
        impact_score_source: 'win_impact_v1_additive',
      },
      score_history: [
        {
          calculated_at: '2026-07-10T00:00:00Z',
          gravity_score: 85.5,
        },
      ],
    })
    expect(detail.sport).toBe('NBA')
    expect(detail.impact_score).toBe(88.4)
    expect(detail.value_score).toBe(88.4)
    expect(detail.impact_sport_percentile).toBe(97)

    const search = mapSearchRowToAthlete({
      id: 'nba2',
      name: 'NBA Search Star',
      sport: 'nba',
      gravity_score: 95.7,
      impact_score: 91.2,
      impact_sport_percentile: 99,
    })
    expect(search.sport).toBe('NBA')
    expect(search.impact_score).toBe(91.2)
    expect(search.value_score).toBe(91.2)
    expect(search.impact_sport_percentile).toBe(99)
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

  it('maps NIL consensus fallback for search rows', () => {
    const rec = mapSearchRowToAthlete({
      id: 'a1',
      name: 'Search Athlete',
      school: 'State U',
      sport: 'cfb',
      dollar_p10_usd: 120000,
      dollar_p50_usd: 200000,
      dollar_p90_usd: 320000,
      nil_valuation_consensus: null,
    })
    expect(rec.nil_valuation_consensus).toBe(200000)
    expect(rec.nil_range_low).toBe(120000)
    expect(rec.nil_range_high).toBe(320000)
  })

  it('maps NIL midpoint fallback when p50 is absent', () => {
    const rec = mapWatchlistAthleteRow({
      athlete_id: 'a2',
      name: 'Watchlist Athlete',
      school: 'State U',
      sport: 'cfb',
      dollar_p10_usd: 100000,
      dollar_p50_usd: null,
      dollar_p90_usd: 300000,
    })
    expect(rec.nil_valuation_consensus).toBe(200000)
  })

  it('maps comparable NIL estimate using fallback chain', () => {
    const fromDeal = mapComparableRow({
      id: 'c1',
      name: 'Comp One',
      deal_value: 450000,
      nil_valuation_consensus: 300000,
      dollar_p50_usd: 250000,
    })
    expect(fromDeal.nil_valuation_consensus).toBe(450000)

    const fromP50 = mapComparableRow({
      id: 'c2',
      name: 'Comp Two',
      nil_valuation_consensus: null,
      dollar_p50_usd: 220000,
      dollar_p10_usd: 100000,
      dollar_p90_usd: 300000,
    })
    expect(fromP50.nil_valuation_consensus).toBe(220000)

    const fromMidpoint = mapComparableRow({
      id: 'c3',
      name: 'Comp Three',
      nil_valuation_consensus: null,
      dollar_p10_usd: 150000,
      dollar_p90_usd: 250000,
    })
    expect(fromMidpoint.nil_valuation_consensus).toBe(200000)
  })

  it('preserves zero NIL values in comparable rows', () => {
    const row = mapComparableRow({
      id: 'c0',
      name: 'Comp Zero',
      nil_valuation_consensus: 0,
    })
    expect(row.nil_valuation_consensus).toBe(0)
  })

  it('maps comparable list NIL estimates from bundle rows', () => {
    const rows = mapComparablesFromBundle(
      [
        {
          id: 'c4',
          name: 'Comp Four',
          nil_valuation_consensus: null,
          nil_valuation_raw: 310000,
        },
      ],
      82,
    )
    expect(rows).toHaveLength(1)
    expect(rows[0]?.nil_valuation_consensus).toBe(310000)
  })

  it('parses currency-formatted NIL strings from backend payloads', () => {
    const rec = mapSearchRowToAthlete({
      id: 'a-money',
      name: 'Money Athlete',
      nil_estimate: '$275,000',
      nil_range_low: '$200,000',
      nil_range_high: '400K',
    })
    expect(rec.nil_valuation_consensus).toBe(275000)
    expect(rec.nil_range_low).toBe(200000)
    expect(rec.nil_range_high).toBe(400000)
  })
})
