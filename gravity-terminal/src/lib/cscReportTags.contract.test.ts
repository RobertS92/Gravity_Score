import { describe, expect, it } from 'vitest'
import {
  classifyConferenceTier,
  classifyConfidenceTag,
  classifyTierTag,
  conferenceTierDisplayLabel,
  shouldSuppressPercentile,
} from './cscReportTags'

describe('classifyTierTag', () => {
  it('maps Top-tier, Mid-tier, Developing, Emerging labels', () => {
    expect(classifyTierTag('Top-tier')).toBe('top')
    expect(classifyTierTag('Mid-tier')).toBe('mid')
    expect(classifyTierTag('Developing')).toBe('developing')
    expect(classifyTierTag('Emerging')).toBe('emerging')
  })

  it('strips trailing asterisk before classifying', () => {
    expect(classifyTierTag('Mid-tier*')).toBe('mid')
    expect(classifyTierTag('Top-tier**')).toBe('top')
  })

  it('returns null for unrecognized or empty values', () => {
    expect(classifyTierTag(null)).toBeNull()
    expect(classifyTierTag('')).toBeNull()
    expect(classifyTierTag('Legacy')).toBeNull()
  })
})

describe('classifyConfidenceTag', () => {
  it('maps High Confidence / Moderate Confidence / Low Confidence', () => {
    expect(classifyConfidenceTag('High Confidence')).toBe('high')
    expect(classifyConfidenceTag('Moderate Confidence')).toBe('moderate')
    expect(classifyConfidenceTag('Low Confidence')).toBe('low')
  })

  it('is case-insensitive', () => {
    expect(classifyConfidenceTag('LOW')).toBe('low')
    expect(classifyConfidenceTag('moderate')).toBe('moderate')
  })

  it('returns null for unknown labels', () => {
    expect(classifyConfidenceTag(undefined)).toBeNull()
    expect(classifyConfidenceTag('Unverified')).toBeNull()
  })
})

describe('classifyConferenceTier', () => {
  it('returns canonical power tokens for power_5/power_4', () => {
    expect(classifyConferenceTier('power_5')).toBe('power_5')
    expect(classifyConferenceTier('POWER_5')).toBe('power_5')
    expect(classifyConferenceTier('power_4')).toBe('power_4')
  })

  it('returns null for unknown tiers', () => {
    expect(classifyConferenceTier('nonsense')).toBeNull()
    expect(classifyConferenceTier(null)).toBeNull()
  })
})

describe('conferenceTierDisplayLabel', () => {
  it('renders friendly labels', () => {
    expect(conferenceTierDisplayLabel('power_5')).toBe('Power 5')
    expect(conferenceTierDisplayLabel('group_of_5')).toBe('Group of 5')
    expect(conferenceTierDisplayLabel('mid_major')).toBe('Mid-Major')
  })

  it('returns null for invalid tier strings', () => {
    expect(conferenceTierDisplayLabel('xyz')).toBeNull()
    expect(conferenceTierDisplayLabel(null)).toBeNull()
  })
})

describe('shouldSuppressPercentile', () => {
  it('suppresses only when cohort_fit is poor', () => {
    expect(shouldSuppressPercentile('poor')).toBe(true)
    expect(shouldSuppressPercentile('Poor')).toBe(true)
    expect(shouldSuppressPercentile('good')).toBe(false)
    expect(shouldSuppressPercentile('edge')).toBe(false)
    expect(shouldSuppressPercentile(null)).toBe(false)
  })
})
