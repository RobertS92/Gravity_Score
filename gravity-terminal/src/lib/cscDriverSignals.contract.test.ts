import { describe, expect, it } from 'vitest'
import { enrichKeyValueDrivers } from './cscDriverSignals'
import type { AthleteRecord } from '../types/athlete'

const athlete: AthleteRecord = {
  athlete_id: 'a1',
  name: 'Arch Manning',
  brand_score: 82.4,
  instagram_followers: 245_000,
  tiktok_followers: null,
  twitter_followers: 12_000,
}

describe('enrichKeyValueDrivers', () => {
  it('keeps Brand Score and prefers live follower counts over N/A', () => {
    const drivers = enrichKeyValueDrivers(
      [
        {
          label: 'Brand Strength',
          signal: 'High',
          explanation: 'Brand leads the profile.',
          supporting_signals: [
            { label: 'Instagram', value: 'N/A' },
            { label: 'TikTok', value: 'N/A' },
          ],
        },
      ],
      athlete,
    )
    const brand = drivers.find((d) => d.label === 'Brand Strength')
    const byLabel = Object.fromEntries((brand?.supporting_signals ?? []).map((s) => [s.label, s.value]))
    expect(byLabel['Brand Score']).toBe('82.4/100')
    expect(byLabel.Instagram).toBe('245K')
    expect(byLabel.TikTok).toBe('N/A')
    expect(byLabel.X).toBe('12K')
  })
})
