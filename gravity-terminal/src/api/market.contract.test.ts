import { beforeEach, describe, expect, it, vi } from 'vitest'

import { getMarketSchools } from './market'
import { apiGet } from './client'

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
})
