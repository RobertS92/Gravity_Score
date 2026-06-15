import { describe, expect, it } from 'vitest'
import {
  formatDriverMetric,
  formatNilRange,
  formatNilRangeAligned,
  formatNilValue,
  isNilRangeEstimate,
} from './formatters'

describe('formatNilValue', () => {
  it('formats sub-million values as thousands', () => {
    expect(formatNilValue(17_900)).toBe('$17.9K')
    expect(formatNilValue(999_400)).toBe('$999.4K')
  })

  it('formats million-plus values as M notation', () => {
    expect(formatNilValue(1_200_000)).toBe('$1.2M')
  })

  it('formats ranges with consistent K/M policy', () => {
    expect(formatNilRange(35_000, 1_200_000)).toBe('RANGE: $35.0K – $1.2M')
  })

  it('shows distinct endpoints when M rounding would collapse a narrow band', () => {
    expect(formatNilRangeAligned(4_530_000, 4_520_000, 4_540_000)).toBe(
      'RANGE: $4520.0K – $4540.0K',
    )
  })

  it('collapses a flat band (<$250 spread) into a single ESTIMATE label', () => {
    expect(formatNilRangeAligned(17_900, 17_900, 17_900)).toBe('ESTIMATE: $17.9K')
    expect(formatNilRangeAligned(2_000_000, 1_999_900, 2_000_050)).toBe('ESTIMATE: $2.0M')
    expect(isNilRangeEstimate(17_900, 17_900)).toBe(true)
    expect(isNilRangeEstimate(100_000, 250_000)).toBe(false)
  })

  it('keeps the range label when the band is meaningfully wide', () => {
    expect(formatNilRangeAligned(100_000, 80_000, 120_000)).toBe('RANGE: $80.0K – $120.0K')
  })
})

describe('formatDriverMetric', () => {
  it('formats followers/reach with K/M notation', () => {
    expect(formatDriverMetric(245_000, 'followers')).toBe('245.0K')
    expect(formatDriverMetric(1_400_000, 'followers')).toBe('1.4M')
    expect(formatDriverMetric(400, 'followers')).toBe('400')
  })

  it('formats percent / score / pts variants', () => {
    expect(formatDriverMetric(6.2, '%')).toBe('6.2%')
    expect(formatDriverMetric(72.4, '/100')).toBe('72.4')
    expect(formatDriverMetric(3.5, 'pts')).toBe('+3.5')
    expect(formatDriverMetric(-2.1, 'pts')).toBe('-2.1')
  })

  it('passes through string values verbatim', () => {
    expect(formatDriverMetric('Active', null)).toBe('Active')
  })

  it('emits an em-dash for null/NaN', () => {
    expect(formatDriverMetric(null, 'followers')).toBe('—')
    expect(formatDriverMetric(undefined, '%')).toBe('—')
    expect(formatDriverMetric(Number.NaN, 'score')).toBe('—')
  })
})
import { formatInteger, formatNilMillions, formatPercent1, formatScore, formatSignedMoneyDelta } from './formatters'

describe('formatters numeric safety', () => {
  it('keeps zero values visible instead of blanking', () => {
    expect(formatScore(0)).toBe('0.0')
    expect(formatNilMillions(0)).toBe('$0.0M')
    expect(formatPercent1(0)).toBe('0.0%')
    expect(formatInteger(0)).toBe('0')
    expect(formatSignedMoneyDelta(0)).toBe('$0')
  })

  it('handles malformed runtime values safely', () => {
    expect(formatScore('bad' as unknown as number)).toBe('—')
    expect(formatNilMillions('200000' as unknown as number)).toBe('$0.2M')
    expect(formatInteger('1200' as unknown as number)).toBe('1,200')
  })
})
