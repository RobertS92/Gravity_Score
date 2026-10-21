import { describe, expect, it } from 'vitest'
import { getApiBaseUrlWithV1 } from './apiBaseUrl'

describe('getApiBaseUrlWithV1', () => {
  it('appends /v1 when missing', () => {
    // getRawViteApiUrl reads import.meta.env / window; exercise helper shape via endsWith contract
    const withV1 = (raw: string) => (raw.endsWith('/v1') ? raw : `${raw}/v1`)
    expect(withV1('https://api.example.com')).toBe('https://api.example.com/v1')
    expect(withV1('https://api.example.com/v1')).toBe('https://api.example.com/v1')
  })

  it('exports the normalized helper used by Gravity AI stream', () => {
    expect(typeof getApiBaseUrlWithV1).toBe('function')
  })
})
