import { parseFiniteNumber } from './numberParsing'

const EM = '\u2014'

export function formatScore(n: number | null | undefined): string {
  const value = parseFiniteNumber(n)
  if (value == null) return EM
  return value.toFixed(1)
}

export function formatDelta(n: number | null | undefined): string {
  const value = parseFiniteNumber(n)
  if (value == null) return EM
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}`
}

export function formatNilMillions(n: number | null | undefined): string {
  const value = parseFiniteNumber(n)
  if (value == null) return EM
  const m = value / 1_000_000
  return `$${m.toFixed(1)}M`
}

export function formatNilRange(low: number | null | undefined, high: number | null | undefined): string {
  const lowValue = parseFiniteNumber(low)
  const highValue = parseFiniteNumber(high)
  const lowDisplay = lowValue == null ? EM : formatNilMillions(lowValue)
  const highDisplay = highValue == null ? EM : formatNilMillions(highValue)
  return `RANGE: ${lowDisplay} \u2013 ${highDisplay}`
}

export function formatInteger(n: number | null | undefined): string {
  const value = parseFiniteNumber(n)
  if (value == null) return 'N/A'
  return new Intl.NumberFormat('en-US').format(Math.round(value))
}

export function formatPercent1(n: number | null | undefined): string {
  const value = parseFiniteNumber(n)
  if (value == null) return EM
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}%`
}

export function formatSignedMoneyDelta(n: number | null | undefined): string {
  const value = parseFiniteNumber(n)
  if (value == null) return EM
  const sign = value > 0 ? '+' : value < 0 ? '\u2212' : ''
  const v = Math.abs(value)
  if (v >= 1_000_000) return `${sign}${(v / 1_000_000).toFixed(1)}M`
  if (v >= 1_000) return `${sign}$${Math.round(v / 1_000)}K`
  return `${sign}$${Math.round(v)}`
}

export { EM }
