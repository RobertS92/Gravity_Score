const EM = '\u2014'

function toFiniteNumber(value: unknown): number | null {
  if (typeof value === 'number') {
    return Number.isFinite(value) ? value : null
  }
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (!trimmed) return null
    const parsed = Number(trimmed)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

export function formatScore(n: number | null | undefined): string {
  const value = toFiniteNumber(n)
  if (value == null) return EM
  return value.toFixed(1)
}

export function formatDelta(n: number | null | undefined): string {
  const value = toFiniteNumber(n)
  if (value == null) return EM
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}`
}

export function formatNilMillions(n: number | null | undefined): string {
  const value = toFiniteNumber(n)
  if (value == null) return EM
  const m = value / 1_000_000
  return `$${m.toFixed(1)}M`
}

export function formatNilRange(low: number | null | undefined, high: number | null | undefined): string {
  if (toFiniteNumber(low) == null || toFiniteNumber(high) == null) return `RANGE: ${EM} \u2013 ${EM}`
  return `RANGE: ${formatNilMillions(low)} \u2013 ${formatNilMillions(high)}`
}

export function formatInteger(n: number | null | undefined): string {
  const value = toFiniteNumber(n)
  if (value == null) return 'N/A'
  return new Intl.NumberFormat('en-US').format(Math.round(value))
}

export function formatPercent1(n: number | null | undefined): string {
  const value = toFiniteNumber(n)
  if (value == null) return EM
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}%`
}

export function formatSignedMoneyDelta(n: number | null | undefined): string {
  const value = toFiniteNumber(n)
  if (value == null) return EM
  const sign = value > 0 ? '+' : value < 0 ? '\u2212' : ''
  const v = Math.abs(value)
  if (v >= 1_000_000) return `${sign}${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `${sign}$${Math.round(v / 1_000)}K`
  return `${sign}$${Math.round(v)}`
}

export { EM }
