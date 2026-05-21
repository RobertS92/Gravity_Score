import { parseFiniteNumber } from './numberParsing'

const EM = '\u2014'
type NilUnit = 'K' | 'M'

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

export function formatNilValue(n: number | null | undefined): string {
  const value = parseFiniteNumber(n)
  if (value == null) return EM
  if (Math.abs(value) < 1_000_000) {
    return `$${(value / 1_000).toFixed(1)}K`
  }
  const m = value / 1_000_000
  // Avoid confusing zeroed-million displays for small values.
  if (Math.abs(m) < 0.05) {
    return `$${(value / 1_000).toFixed(1)}K`
  }
  return `$${m.toFixed(1)}M`
}

export function selectNilDisplayUnit(n: number | null | undefined): NilUnit {
  const value = parseFiniteNumber(n)
  if (value == null) return 'K'
  return Math.abs(value) >= 1_000_000 ? 'M' : 'K'
}

export function formatNilValueInUnit(n: number | null | undefined, unit: NilUnit): string {
  const value = parseFiniteNumber(n)
  if (value == null) return EM
  if (unit === 'M') return `$${(value / 1_000_000).toFixed(1)}M`
  return `$${(value / 1_000).toFixed(1)}K`
}

export function formatNilRangeAligned(
  benchmark: number | null | undefined,
  low: number | null | undefined,
  high: number | null | undefined,
): string {
  const unit = selectNilDisplayUnit(benchmark)
  return `RANGE: ${formatNilValueInUnit(low, unit)} \u2013 ${formatNilValueInUnit(high, unit)}`
}

export function formatNilRange(low: number | null | undefined, high: number | null | undefined): string {
  const lowValue = parseFiniteNumber(low)
  const highValue = parseFiniteNumber(high)
  const lowDisplay = lowValue == null ? EM : formatNilValue(lowValue)
  const highDisplay = highValue == null ? EM : formatNilValue(highValue)
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
