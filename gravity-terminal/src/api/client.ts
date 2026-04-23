import { mockRequest } from '../mocks/handlers'
import { getApiBaseUrlWithV1 } from '../lib/apiBaseUrl'

/** API root must include `/v1`. If the URL is `http://host:8000`, we append `/v1`. */
export function getApiBaseUrl(): string {
  return getApiBaseUrlWithV1()
}

const USE_MOCKS = import.meta.env.VITE_USE_MOCKS === 'true'
const ENV_TOKEN = (import.meta.env.VITE_API_BEARER_TOKEN as string | undefined) ?? ''

const SESSION_KEY = 'gravity_access_token'

export function getSessionToken(): string {
  try {
    return localStorage.getItem(SESSION_KEY) ?? ''
  } catch {
    return ''
  }
}

export function setSessionToken(token: string) {
  try {
    if (token) localStorage.setItem(SESSION_KEY, token)
    else localStorage.removeItem(SESSION_KEY)
  } catch {
    /* ignore */
  }
}

function authHeader(): string {
  const session = getSessionToken()
  return session || ENV_TOKEN
}

function headers(): HeadersInit {
  const h: Record<string, string> = { Accept: 'application/json' }
  const t = authHeader()
  if (t) h.Authorization = `Bearer ${t}`
  return h
}

export async function apiGet<T>(path: string): Promise<T> {
  const rel = path.startsWith('/') ? path.slice(1) : path
  if (USE_MOCKS) {
    return mockRequest('GET', rel) as Promise<T>
  }
  const base = getApiBaseUrl()
  if (!base) throw new Error('VITE_API_URL is not set')
  const r = await fetch(`${base}/${rel}`, { headers: headers() })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json() as Promise<T>
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  const rel = path.startsWith('/') ? path.slice(1) : path
  if (USE_MOCKS) {
    return mockRequest('POST', rel, body) as Promise<T>
  }
  const base = getApiBaseUrl()
  if (!base) throw new Error('VITE_API_URL is not set')
  const r = await fetch(`${base}/${rel}`, {
    method: 'POST',
    headers: { ...headers(), 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json() as Promise<T>
}

export async function apiPatch<T>(path: string, body: unknown): Promise<T> {
  const rel = path.startsWith('/') ? path.slice(1) : path
  if (USE_MOCKS) {
    return mockRequest('PATCH', rel, body) as Promise<T>
  }
  const base = getApiBaseUrl()
  if (!base) throw new Error('VITE_API_URL is not set')
  const r = await fetch(`${base}/${rel}`, {
    method: 'PATCH',
    headers: { ...headers(), 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json() as Promise<T>
}

export async function apiDelete<T>(path: string): Promise<T> {
  const rel = path.startsWith('/') ? path.slice(1) : path
  if (USE_MOCKS) {
    return mockRequest('DELETE', rel) as Promise<T>
  }
  const base = getApiBaseUrl()
  if (!base) throw new Error('VITE_API_URL is not set')
  const r = await fetch(`${base}/${rel}`, { method: 'DELETE', headers: headers() })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json() as Promise<T>
}

export function isMockMode() {
  return USE_MOCKS
}
