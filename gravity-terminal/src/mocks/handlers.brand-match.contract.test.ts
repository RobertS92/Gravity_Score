import { describe, expect, it } from 'vitest'
import type { BrandMatchBrief, BrandMatchResponse, BrandMatchResult } from '../types/reports'
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

function matchesOf(raw: unknown): BrandMatchResult[] {
  if (Array.isArray(raw)) return raw as BrandMatchResult[]
  return ((raw as BrandMatchResponse)?.matches ?? []) as BrandMatchResult[]
}

describe('brand match mock handler', () => {
  it('returns broad result set larger than watchlist', async () => {
    const raw = await mockRequest('POST', 'reports/brand-match', BASE_BRIEF)
    const rows = matchesOf(raw)
    expect(rows.length).toBeGreaterThan(5)
    expect((raw as BrandMatchResponse).diagnostics).toBeTruthy()
  })

  it('returns athletes for default $400K apparel Southeast brief', async () => {
    const raw = await mockRequest('POST', 'reports/brand-match', {
      ...BASE_BRIEF,
      budget: 400_000,
    })
    expect(matchesOf(raw).length).toBeGreaterThan(0)
  })

  it('respects budget ceiling with +20% guard', async () => {
    const raw = await mockRequest('POST', 'reports/brand-match', {
      ...BASE_BRIEF,
      budget: 200_000,
    })
    const rows = matchesOf(raw)
    for (const row of rows) {
      if (typeof row.deal_range_low === 'number' && typeof row.deal_range_high === 'number') {
        const p50 = (row.deal_range_low + row.deal_range_high) / 2
        expect(p50).toBeLessThanOrEqual(240_000)
      }
    }
  })

  it('changes ordering when prioritize engagement is enabled', async () => {
    const normal = matchesOf(
      await mockRequest('POST', 'reports/brand-match', {
        ...BASE_BRIEF,
        prioritize_engagement: false,
      }),
    )
    const engagement = matchesOf(
      await mockRequest('POST', 'reports/brand-match', {
        ...BASE_BRIEF,
        prioritize_engagement: true,
      }),
    )
    expect(normal[0]?.athlete_id).not.toBe(engagement[0]?.athlete_id)
  })
})
