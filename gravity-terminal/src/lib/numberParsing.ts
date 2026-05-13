export function parseFiniteNumber(value: unknown): number | null {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null
  }
  if (typeof value !== 'string') return null

  const raw = value.trim()
  if (!raw) return null

  let normalized = raw.replace(/\u2212/g, '-')
  let negative = false
  if (normalized.startsWith('(') && normalized.endsWith(')')) {
    negative = true
    normalized = normalized.slice(1, -1).trim()
  }

  normalized = normalized
    .replace(/\$/g, '')
    .replace(/,/g, '')
    .replace(/_/g, '')
    .replace(/\s+/g, '')

  let multiplier = 1
  const suffix = normalized.slice(-1).toLowerCase()
  if (suffix === 'k' || suffix === 'm' || suffix === 'b') {
    multiplier = suffix === 'k' ? 1_000 : suffix === 'm' ? 1_000_000 : 1_000_000_000
    normalized = normalized.slice(0, -1)
  }

  if (normalized.endsWith('%')) {
    normalized = normalized.slice(0, -1)
  }

  if (!/^[-+]?(?:\d+\.?\d*|\.\d+)(?:e[-+]?\d+)?$/i.test(normalized)) {
    return null
  }

  const parsed = Number(normalized) * multiplier
  if (!Number.isFinite(parsed)) return null
  return negative ? -parsed : parsed
}
