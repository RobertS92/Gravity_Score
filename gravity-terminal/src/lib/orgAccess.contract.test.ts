import { describe, expect, it } from 'vitest'
import {
  ILLUSTRATIVE_CAP_FIGURES,
  capiqFeaturesForMembership,
  centsToDollars,
  formatAccountRole,
  membershipStatusLabel,
  resolveMissingOrgAccessSteps,
  sampleCapFigureLabel,
} from './orgAccess'

describe('orgAccess', () => {
  it('labels roles for Settings / CapIQ', () => {
    expect(formatAccountRole('school_admin')).toBe('School admin')
    expect(formatAccountRole(null)).toBe('Not set')
  })

  it('distinguishes profile label from CapIQ membership in resolve steps', () => {
    const steps = resolveMissingOrgAccessSteps({
      organizationId: null,
      orgType: 'school',
      profileOrgName: 'SMU',
    })
    expect(steps.some((s) => s.includes('profile label'))).toBe(true)
    expect(steps.some((s) => s.includes('SMU'))).toBe(true)
    expect(membershipStatusLabel(false)).toBe('Not linked')
  })

  it('lists locked CapIQ features when unlinked', () => {
    const features = capiqFeaturesForMembership(false, 'agent')
    expect(features.every((f) => f.toLowerCase().includes('locked'))).toBe(true)
  })

  it('marks illustrative cap figures as SAMPLE — never as school data', () => {
    expect(ILLUSTRATIVE_CAP_FIGURES.totalBudgetDollars).toBe(15_000_000)
    expect(ILLUSTRATIVE_CAP_FIGURES.committedDollars).toBe(11_240_000)
    expect(sampleCapFigureLabel('budget')).toMatch(/^SAMPLE/)
    expect(sampleCapFigureLabel('committed')).toMatch(/not your school/)
  })

  it('converts utilization cents to dollars', () => {
    expect(centsToDollars(1_500_000_00)).toBe(1_500_000)
    expect(centsToDollars(null)).toBeNull()
  })
})
