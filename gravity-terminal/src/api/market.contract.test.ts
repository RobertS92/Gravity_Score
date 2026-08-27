import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getMarketScan, getMarketSchools } from './market'
import { apiGet } from './client'

vi.mock('./client', () => ({
  apiGet: vi.fn(),
}))

vi.mock('./client', () => ({
  apiGet: vi.fn(),
}))

describe('market api adapters', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('maps program gravity score fields for school rows', async () => {
    vi.mocked(apiGet).mockResolvedValue({
      schools: [
        {
          team_id: 'team-1',
          school: 'State U',
          conference: 'SEC',
          sport: 'cfb',
          avg_gravity_score: 71.2,
          program_gravity_score: 84.6,
          program_brand_score: 79.5,
          program_proof_score: 82.1,
          program_velocity_score: 74.2,
          program_risk_score: 88.4,
          athlete_count: 85,
          watchlisted_count: 6,
          top_athlete_name: 'A. Player',
          nil_market_size_estimate: 2500000,
        },
      ],
    })

    const schools = await getMarketSchools()

    expect(schools).toHaveLength(1)
    expect(schools[0]).toMatchObject({
      team_id: 'team-1',
      school: 'State U',
      conference: 'SEC',
      sport: 'cfb',
      avg_gravity_score: 71.2,
      program_gravity_score: 84.6,
      program_brand_score: 79.5,
      program_proof_score: 82.1,
      program_velocity_score: 74.2,
      program_risk_score: 88.4,
      athlete_count: 85,
      watchlisted_count: 6,
      top_athlete_name: 'A. Player',
      nil_market_size_estimate: 2500000,
    })
  })

  it('falls back to avg gravity when program gravity is absent', async () => {
    vi.mocked(apiGet).mockResolvedValue({
      schools: [
        {
          school: 'Fallback U',
          sport: 'cfb',
          avg_gravity_score: 69.4,
          program_gravity_score: null,
        },
      ],
    })

    const schools = await getMarketSchools()

    expect(schools).toHaveLength(1)
    expect(schools[0]).toMatchObject({
      school: 'Fallback U',
      sport: 'cfb',
      avg_gravity_score: 69.4,
      program_gravity_score: 69.4,
    })
  })

  it('parses formatted numeric fields from market schools payload', async () => {
    vi.mocked(apiGet).mockResolvedValue({
      schools: [
        {
          school: 'Format U',
          sport: 'cfb',
          program_gravity_score: '84.6',
          nil_market_size_estimate: '$2.5M',
        },
      ],
    })

    const schools = await getMarketSchools()

    expect(schools[0]).toMatchObject({
      school: 'Format U',
      program_gravity_score: 84.6,
      nil_market_size_estimate: 2500000,
    })
  })

  it('retries with include_stale_roster when the live window is empty', async () => {
    vi.mocked(apiGet)
      .mockResolvedValueOnce({ athletes: [], total: 0, returned: 0, roster_window: 'live' })
      .mockResolvedValueOnce({
        athletes: [
          {
            id: 'ath-1',
            name: 'A. Player',
            school: 'State U',
            gravity_score: 81,
          },
        ],
        total: 1,
        returned: 1,
        roster_window: 'stale',
      })

    const pages: number[] = []
    const result = await getMarketScan({ sports: 'CFB' }, { onPage: (p) => pages.push(p.athletes.length) })

    expect(vi.mocked(apiGet).mock.calls[0][0]).toContain('market/scan?')
    expect(vi.mocked(apiGet).mock.calls[0][0]).not.toContain('include_stale_roster=true')
    expect(vi.mocked(apiGet).mock.calls[1][0]).toContain('include_stale_roster=true')
    expect(result.athletes).toHaveLength(1)
    expect(result.athletes[0]?.name).toBe('A. Player')
    expect(result.total).toBe(1)
    expect(result.rosterWindow).toBe('stale')
    expect(pages[0]).toBe(1)
  })

  it('keeps live rows without a stale retry', async () => {
    vi.mocked(apiGet).mockResolvedValue({
      athletes: [{ id: 'ath-2', name: 'Fresh Player', gravity_score: 90 }],
      total: 1,
      returned: 1,
      roster_window: 'live',
    })

    const result = await getMarketScan({ sports: 'CFB' })

    expect(apiGet).toHaveBeenCalledTimes(1)
    expect(result.rosterWindow).toBe('live')
    expect(result.athletes[0]?.name).toBe('Fresh Player')
  })

  it('honors maxLoaded for agent-sized scans', async () => {
    vi.mocked(apiGet).mockResolvedValue({
      athletes: [{ id: 'ath-3', name: 'Capped', gravity_score: 70 }],
      total: 4000,
      returned: 1,
      roster_window: 'stale_fallback',
    })

    const result = await getMarketScan({ maxLoaded: 1 })

    expect(apiGet).toHaveBeenCalledTimes(1)
    expect(String(vi.mocked(apiGet).mock.calls[0][0])).toContain('limit=1')
    expect(result.athletes).toHaveLength(1)
    expect(result.rosterWindow).toBe('stale_fallback')
  })
})
