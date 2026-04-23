declare global {
  interface Window {
    /** Set by `public/env-config.js` (local) or Docker entrypoint (production). */
    __GRAVITY_API_URL__?: string
  }
}

/** Raw API origin from runtime script (Docker) or Vite env (dev / optional build-time). */
export function getRawViteApiUrl(): string {
  if (typeof window !== 'undefined') {
    const w = window.__GRAVITY_API_URL__
    if (typeof w === 'string' && w.trim() !== '') {
      return w.trim().replace(/\/$/, '')
    }
  }
  return (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? ''
}

/** API root including `/v1` when missing. */
export function getApiBaseUrlWithV1(): string {
  const raw = getRawViteApiUrl()
  if (!raw) return ''
  if (raw.endsWith('/v1')) return raw
  return `${raw}/v1`
}
