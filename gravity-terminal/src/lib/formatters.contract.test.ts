import { describe, expect, it } from 'vitest'
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
