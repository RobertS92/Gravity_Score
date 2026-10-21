import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'

import { ILLUSTRATIVE_CAP_FIGURES, sampleCapFigureLabel } from '../../lib/orgAccess'
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

describe('RightPanel Cap rail — no unlabeled sample dollars', () => {
  it('does not hard-code the former $15M / $11.2M demo figures in the Cap rail', () => {
    const src = readFileSync(join(dirname(fileURLToPath(import.meta.url)), 'RightPanel.tsx'), 'utf8')
    expect(src).not.toContain('15_000_000')
    expect(src).not.toContain('11_240_000')
    expect(src).not.toContain('3_760_000')
    expect(src).not.toMatch(/wires to/i)
    expect(src).toContain('No organization linked')
    expect(src).toContain('fetchCapUtilization')
  })

  it('keeps illustrative constants explicitly SAMPLE-labeled for any future demo UI', () => {
    expect(ILLUSTRATIVE_CAP_FIGURES.totalBudgetDollars).toBe(15_000_000)
    expect(sampleCapFigureLabel('budget')).toMatch(/^SAMPLE/)
  })
})
