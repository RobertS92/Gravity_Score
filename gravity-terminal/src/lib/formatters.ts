const EM = '\u2014'

export function formatScore(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return EM
  return n.toFixed(1)
}

export function formatDelta(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return EM
  const sign = n > 0 ? '+' : ''
  return `${sign}${n.toFixed(1)}`
}

export function formatNilMillions(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return EM
  const m = n / 1_000_000
  return `$${m.toFixed(1)}M`
}

export function formatNilRange(low: number | null | undefined, high: number | null | undefined): string {
  if (low == null || high == null) return `RANGE: ${EM} \u2013 ${EM}`
  return `RANGE: ${formatNilMillions(low)} \u2013 ${formatNilMillions(high)}`
}

export function formatInteger(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return 'N/A'
  return new Intl.NumberFormat('en-US').format(Math.round(n))
}

export function formatPercent1(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return EM
  const sign = n > 0 ? '+' : ''
  return `${sign}${n.toFixed(1)}%`
}

export function formatSignedMoneyDelta(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return EM
  const sign = n > 0 ? '+' : n < 0 ? '\u2212' : ''
  const v = Math.abs(n)
  if (v >= 1_000_000) return `${sign}${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `${sign}$${Math.round(v / 1_000)}K`
  return `${sign}$${Math.round(v)}`
}

export { EM }
