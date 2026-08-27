import { describe, expect, it } from 'vitest'
import {
  dealConfidenceCopy,
  dealEvidenceCopy,
  dealScopeCopy,
  driverNarrativeConflictsBadge,
  EVIDENCE_CALIBRATION_THRESHOLD,
  fallbackTakeaway,
  isPlanningEstimateExport,
  shouldShowTierBadge,
  titleCaseChip,
  yearlyOfferConflationReason,
} from './cscDealCopy'
import { qualifyDriverDisplay } from './cscDriverSignals'
import type { CscKeyValueDriver } from '../types/reports'

describe('dealScopeCopy', () => {
  it('explains a standard activation in deal language', () => {
    expect(dealScopeCopy('standard_activation').menuLabel).toMatch(/campaign/i)
    expect(dealScopeCopy('standard_activation').blurb.toLowerCase()).toContain('activation')
  })

  it('falls back to a standard campaign for unknown scopes', () => {
    expect(dealScopeCopy('not_a_scope').menuLabel).toBe(dealScopeCopy('standard_activation').menuLabel)
  })
})

describe('dealConfidenceCopy', () => {
  it('keeps a hedge clause in the uncalibrated label itself', () => {
    const copy = dealConfidenceCopy('Uncalibrated')
    expect(copy.title).toMatch(/planning estimate/i)
    expect(copy.title.toLowerCase()).toContain('not yet backed by closed deals')
    expect(copy.tier).toBe('uncalibrated')
  })

  it('keeps high/moderate/low readable from the label alone', () => {
    expect(dealConfidenceCopy('High').title).toMatch(/^High confidence/i)
    expect(dealConfidenceCopy('Moderate Confidence').title).toMatch(/^Moderate confidence/i)
    expect(dealConfidenceCopy('low').title).toMatch(/^Low confidence/i)
    expect(dealConfidenceCopy('low').title.toLowerCase()).toContain('directional')
  })
})

describe('dealEvidenceCopy', () => {
  it('always interpolates a numeric count against the calibration threshold', () => {
    const zero = dealEvidenceCopy(0, 'insufficient_data')
    expect(zero.detail).toContain('0 of 100 qualified transactions')
    expect(zero.count).toBe(0)
    expect(zero.threshold).toBe(EVIDENCE_CALIBRATION_THRESHOLD)

    const some = dealEvidenceCopy(12, 'insufficient_data')
    expect(some.detail).toContain('12 of 100 qualified transactions')

    const prod = dealEvidenceCopy(320, 'production')
    expect(prod.detail).toContain('320 of 100 qualified transactions')
    expect(prod.title).toBe('Calibrated')
  })
})

describe('fallbackTakeaway', () => {
  it('writes a takeaway that leads with yearly value vs campaign offer', () => {
    const text = fallbackTakeaway('Arch Manning', '$21.9M', '$167.9K', '$612.2K')
    expect(text).toContain('yearly market value')
    expect(text).toContain('Suggested offer')
    expect(text).not.toMatch(/benchmark/i)
    expect(yearlyOfferConflationReason(text)).toBeNull()
  })

  it('rejects copy that treats yearly value and offer as one figure', () => {
    expect(
      yearlyOfferConflationReason(
        'The recommended deal range brackets the yearly market value of $21.9M.',
      ),
    ).not.toBeNull()
  })
})

describe('shouldShowTierBadge', () => {
  it('suppresses a confident tier claim when cohort n is 0', () => {
    expect(
      shouldShowTierBadge({ cohortSize: 0, comparableState: 'none', lowCohortData: true }),
    ).toBe(false)
  })

  it('allows a tier badge when the peer set is real', () => {
    expect(
      shouldShowTierBadge({ cohortSize: 12, comparableState: 'sufficient', lowCohortData: false }),
    ).toBe(true)
  })
})

describe('driverNarrativeConflictsBadge', () => {
  it('flags a Low risk badge against elevating narrative language', () => {
    expect(
      driverNarrativeConflictsBadge(
        'Risk',
        'Low',
        'Elevated exposure warrants defensive deal construction and shorter terms.',
      ),
    ).toBe(true)
    expect(
      driverNarrativeConflictsBadge('Risk', 'Low', 'Roster status is stable and modeled risk is contained.'),
    ).toBe(false)
  })
})

describe('qualifyDriverDisplay', () => {
  it('qualifies a High grade when listed signals are mostly N/A', () => {
    const driver: CscKeyValueDriver = {
      label: 'Momentum',
      signal: 'High',
      explanation: 'Modeled velocity is high.',
      supporting_signals: [
        { label: '30d NIL delta', value: 'N/A' },
        { label: '30d Gravity delta', value: 'N/A' },
        { label: 'Velocity score', value: 'N/A' },
      ],
    }
    const display = qualifyDriverDisplay(driver)
    expect(display.signal).toBe('High')
    expect(display.qualifier).toMatch(/modeled, not observed/i)
  })
})

describe('isPlanningEstimateExport', () => {
  it('watermarks uncalibrated and sub-threshold evidence', () => {
    expect(isPlanningEstimateExport('Uncalibrated', 0)).toBe(true)
    expect(isPlanningEstimateExport('Low', 40)).toBe(true)
    expect(isPlanningEstimateExport('High', 320)).toBe(false)
  })
})

describe('titleCaseChip', () => {
  it('normalizes badge casing', () => {
    expect(titleCaseChip('LIMITED COMPS')).toBe('Limited Comps')
    expect(titleCaseChip('UNUSUAL VS PEERS')).toBe('Unusual vs Peers')
  })
})
