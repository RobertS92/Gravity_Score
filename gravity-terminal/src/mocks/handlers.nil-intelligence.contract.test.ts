import { describe, expect, it } from 'vitest'
import type {
  AlternativesResponse,
  ConfidenceResponse,
  DealActionResponse,
} from '../types/nilIntelligence'
import { ARCH_MANNING_ID } from './fixtures'
import { mockRequest } from './handlers'

describe('nil intelligence mock handlers', () => {
  it('returns deal action payload', async () => {
    const raw = await mockRequest('GET', `athletes/${ARCH_MANNING_ID}/deal-action`)
    const res = raw as DealActionResponse
    expect(res.athlete_id).toBe(ARCH_MANNING_ID)
    expect(res.recommendation).toBeTruthy()
    expect(res.recommended_range_low_usd).toBeGreaterThan(0)
    expect(res.recommended_range_high_usd).toBeGreaterThan(res.recommended_range_low_usd)
    expect(res.rationale.length).toBeGreaterThan(0)
  })

  it('returns confidence payload', async () => {
    const raw = await mockRequest('GET', `athletes/${ARCH_MANNING_ID}/confidence`)
    const res = raw as ConfidenceResponse
    expect(res.athlete_id).toBe(ARCH_MANNING_ID)
    expect(res.overall_score).toBeGreaterThan(0)
    expect(res.overall_score).toBeLessThanOrEqual(1)
    expect(res.factors.length).toBeGreaterThan(0)
  })

  it('returns alternatives payload', async () => {
    const raw = await mockRequest('GET', `athletes/${ARCH_MANNING_ID}/alternatives`)
    const res = raw as AlternativesResponse
    expect(res.athlete_id).toBe(ARCH_MANNING_ID)
    expect(res.alternatives.length).toBeGreaterThan(0)
    expect(res.alternatives[0].athlete_id).not.toBe(ARCH_MANNING_ID)
  })

  it('rejects unknown athlete id for new endpoints', async () => {
    const unknown = 'unknown-athlete'
    await expect(mockRequest('GET', `athletes/${unknown}/deal-action`)).rejects.toThrow(/not found/i)
    await expect(mockRequest('GET', `athletes/${unknown}/confidence`)).rejects.toThrow(/not found/i)
    await expect(mockRequest('GET', `athletes/${unknown}/alternatives`)).rejects.toThrow(/not found/i)
  })
})
