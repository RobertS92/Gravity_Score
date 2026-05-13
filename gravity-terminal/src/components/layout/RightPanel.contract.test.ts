import { describe, expect, it } from 'vitest'

import { getShortlistBudgetEstimate } from './RightPanel'

describe('RightPanel brand-match safety', () => {
  it('returns zero for malformed shortlist payloads', () => {
    expect(getShortlistBudgetEstimate(null)).toBe(0)
    expect(getShortlistBudgetEstimate(undefined)).toBe(0)
    expect(getShortlistBudgetEstimate({})).toBe(0)
    expect(getShortlistBudgetEstimate('bad')).toBe(0)
  })

  it('sums only valid NIL ranges for budget estimate', () => {
    const estimate = getShortlistBudgetEstimate([
      { athlete_id: 'a1', deal_range_low: 100_000, deal_range_high: 200_000 },
      { athlete_id: 'a2', deal_range_low: 300_000, deal_range_high: 500_000 },
      { athlete_id: 'a3', deal_range_low: null, deal_range_high: 100_000 },
      null,
    ])

    expect(estimate).toBe(550_000)
  })
})
