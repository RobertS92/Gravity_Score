import { describe, expect, it } from 'vitest'
import { toSafeAlternatives } from './AlternativesPanel'
import { toSafeConfidenceView } from './ConfidenceCard'
import { toSafeDealActionView } from './DealActionPanel'

describe('nil intelligence panel safety', () => {
  it('normalizes malformed deal-action payloads without throwing', () => {
    const view = toSafeDealActionView({
      recommendation: null,
      structure: null,
      rationale: 'not-an-array',
    })
    expect(view.recommendation).toBe('PASS')
    expect(view.structureType).toBe('N/A')
    expect(view.rationale).toEqual(['not-an-array'])
  })

  it('maps production backend deal-action payload shape', () => {
    const view = toSafeDealActionView({
      recommendation: 'RAISE',
      current_range_low: '$250,000',
      current_range_high: '350000',
      walk_away_price: '400000',
      structure: { type: 'hybrid', term_months: '12' },
      rationale: 'Model says pricing pressure is increasing.',
    })
    expect(view.recommendedLow).toBe(250000)
    expect(view.recommendedHigh).toBe(350000)
    expect(view.walkAway).toBe(400000)
    expect(view.structureType).toBe('HYBRID')
    expect(view.rationale).toEqual(['Model says pricing pressure is increasing.'])
  })

  it('normalizes malformed confidence payloads without throwing', () => {
    const view = toSafeConfidenceView({
      overall_score: '0.84',
      overall_label: null,
      factors: [{ key: 'f1', score: '0.45' }, null],
      caveats: [null, 'Low sample size'],
    })
    expect(view.overallScore).toBeCloseTo(0.84)
    expect(view.overallLabel).toBe('LOW')
    expect(view.factors[0]?.score).toBeCloseTo(0.45)
    expect(view.caveats).toEqual(['Low sample size'])
  })

  it('maps production backend confidence payload shape', () => {
    const view = toSafeConfidenceView({
      score: '0.64',
      level: 'medium',
      factors: [{ name: 'Comparable depth', impact: 'positive' }],
      caveats: ['Limited recent verified deals'],
    })
    expect(view.overallScore).toBeCloseTo(0.64)
    expect(view.overallLabel).toBe('MEDIUM')
    expect(view.factors[0]?.label).toBe('Comparable depth')
    expect(view.factors[0]?.impact).toBe('POSITIVE')
  })

  it('normalizes malformed alternatives payloads without throwing', () => {
    const rows = toSafeAlternatives({
      alternatives: [{ athlete_id: null, name: '', fit_score: '0', nil_valuation_consensus: '0' }, null],
    })
    expect(rows).toHaveLength(2)
    expect(rows[0]?.athleteId).toBe('alt-0')
    expect(rows[0]?.nilConsensus).toBe(0)
    expect(rows[0]?.fitScore).toBe(0)
    expect(rows[1]?.name).toBe('Unknown')
  })

  it('maps production backend alternatives payload shape', () => {
    const rows = toSafeAlternatives({
      candidates: [{ athlete_id: 'a-1', name: 'Comp', nil_estimate: '$175,000', fit_score: 72 }],
    })
    expect(rows).toHaveLength(1)
    expect(rows[0]?.athleteId).toBe('a-1')
    expect(rows[0]?.nilConsensus).toBe(175000)
  })
})
