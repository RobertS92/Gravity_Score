import { describe, expect, it } from 'vitest'
import type { CscReportComparablesRow } from '../types/reports'
import {
  DEAL_STRUCTURE_FALLBACK,
  SOURCE_FALLBACK,
  formatComparableConfidence,
  normalizeComparableConfidence,
  normalizeComparableRow,
  withLegacyOption,
  DEAL_STRUCTURE_GROUPS,
} from './cscComparables'

describe('normalizeComparableConfidence', () => {
  it('normalizes fractional, percent, and basis-point scales', () => {
    expect(normalizeComparableConfidence(0.8198)).toBeCloseTo(0.8198)
    expect(normalizeComparableConfidence(81.98)).toBeCloseTo(0.8198)
    expect(normalizeComparableConfidence(8198)).toBeCloseTo(0.8198)
  })

  it('clamps and handles invalid values safely', () => {
    expect(normalizeComparableConfidence(-4)).toBe(0)
    expect(normalizeComparableConfidence(Number.NaN)).toBeNull()
    expect(normalizeComparableConfidence(null)).toBeNull()
  })

  it('formats confidence for UI display', () => {
    expect(formatComparableConfidence(81.98)).toBe('82%')
    expect(formatComparableConfidence(null)).toBe('\u2014')
  })
})

describe('normalizeComparableRow', () => {
  it('maps legacy backend values to canonical dropdown values', () => {
    const row = normalizeComparableRow({
      athlete_id: 'ath-1',
      name: 'Athlete',
      deal_structure: 'fixed fee',
      verified_source: 'verified deal',
      confidence: 8198,
    })
    expect(row.deal_structure).toBe('Cash / Flat Fee')
    expect(row.verified_source).toBe('Direct Verification')
    expect(row.confidence).toBeCloseTo(0.8198)
  })

  it('fills NIL estimate via fallback chain for blank comparable rows', () => {
    const fromDealValue = normalizeComparableRow({
      athlete_id: 'ath-nil-1',
      name: 'Athlete',
      nil_valuation_consensus: null,
      deal_value: 600000,
      dollar_p50_usd: 450000,
    } as unknown as CscReportComparablesRow)
    expect(fromDealValue.nil_valuation_consensus).toBe(600000)

    const fromMidpoint = normalizeComparableRow({
      athlete_id: 'ath-nil-2',
      name: 'Athlete',
      nil_valuation_consensus: null,
      dollar_p10_usd: 100000,
      dollar_p90_usd: 300000,
    } as unknown as CscReportComparablesRow)
    expect(fromMidpoint.nil_valuation_consensus).toBe(200000)
  })

  it('preserves zero NIL estimate values', () => {
    const row = normalizeComparableRow({
      athlete_id: 'ath-zero',
      name: 'Athlete',
      nil_valuation_consensus: 0,
    })
    expect(row.nil_valuation_consensus).toBe(0)
  })

  it('fills missing text with fallbacks', () => {
    const row = normalizeComparableRow({
      athlete_id: 'ath-2',
      name: 'Athlete',
      deal_structure: '',
      verified_source: '',
      confidence: undefined,
    })
    expect(row.deal_structure).toBe(DEAL_STRUCTURE_FALLBACK)
    expect(row.verified_source).toBe(SOURCE_FALLBACK)
    expect(row.confidence).toBeNull()
  })
})

describe('withLegacyOption', () => {
  it('injects unknown values as readonly legacy options', () => {
    const legacy = withLegacyOption(DEAL_STRUCTURE_GROUPS, 'Cash + merch + streaming rev-share')
    expect(legacy.value).toBe('Cash + merch + streaming rev-share')
    expect(legacy.groups[0]?.label).toBe('Legacy / Imported')
  })
})
