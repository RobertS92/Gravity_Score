import { describe, expect, it } from 'vitest'
import type { BrandMatchBrief, BrandMatchResult } from '../types/reports'
import { mockRequest } from './handlers'

const BASE_BRIEF: BrandMatchBrief = {
  budget: 800_000,
  category: 'apparel',
  geography: ['Southeast'],
  audience: ['18-24'],
  risk_tolerance: 0.5,
  max_transfer_risk: false,
  authenticity_weight: 0.6,
  min_social_reach: 0,
  prioritize_engagement: false,
  excluded_categories: [],
  deal_density_preference: 'any',
}

describe('brand match mock handler', () => {
  it('returns broad result set larger than watchlist', async () => {
    const raw = await mockRequest('POST', 'reports/brand-match', BASE_BRIEF)
    const rows = raw as BrandMatchResult[]
    expect(rows.length).toBeGreaterThan(5)
  })

  it('respects budget ceiling with +20% guard', async () => {
    const raw = await mockRequest('POST', 'reports/brand-match', {
      ...BASE_BRIEF,
      budget: 200_000,
    })
    const rows = raw as BrandMatchResult[]
    for (const row of rows) {
      if (typeof row.deal_range_low === 'number' && typeof row.deal_range_high === 'number') {
        const p50 = (row.deal_range_low + row.deal_range_high) / 2
        expect(p50).toBeLessThanOrEqual(240_000)
      }
    }
  })

  it('changes ordering when prioritize engagement is enabled', async () => {
    const normal = (await mockRequest('POST', 'reports/brand-match', {
      ...BASE_BRIEF,
      prioritize_engagement: false,
    })) as BrandMatchResult[]
    const engagement = (await mockRequest('POST', 'reports/brand-match', {
      ...BASE_BRIEF,
      prioritize_engagement: true,
    })) as BrandMatchResult[]
    expect(normal[0]?.athlete_id).not.toBe(engagement[0]?.athlete_id)
  })
})
