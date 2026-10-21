import { describe, expect, it } from 'vitest'
import {
  KEVIN_JENNINGS_ID,
  mockAthletesById,
  mockSchoolIndex,
  searchMockAthletesByName,
} from './fixtures'
import { mockRequest } from './handlers'

describe('SMU demo cohort mocks', () => {
  it('includes Kevin Jennings in fixtures and name search', () => {
    const ath = mockAthletesById[KEVIN_JENNINGS_ID]
    expect(ath?.name).toBe('Kevin Jennings')
    expect(ath?.school).toBe('SMU')
    expect(ath?.position).toBe('QB')
    expect(ath?.sport).toBe('CFB')

    const hits = searchMockAthletesByName('Jennings')
    expect(hits.some((a) => a.athlete_id === KEVIN_JENNINGS_ID)).toBe(true)
  })

  it('lists SMU on school index', () => {
    expect(mockSchoolIndex.some((r) => r.school === 'SMU' && r.sport === 'cfb')).toBe(true)
  })

  it('Find Player API mock returns Jennings for CFB', async () => {
    const raw = (await mockRequest(
      'GET',
      'athletes?q=Jennings&sports=CFB',
    )) as { athletes: { athlete_id: string; name: string }[] }
    expect(raw.athletes.some((a) => a.name === 'Kevin Jennings')).toBe(true)
  })
})
