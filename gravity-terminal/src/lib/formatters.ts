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

function formatNilBandEndpoints(
  benchmark: number | null | undefined,
  low: number | null | undefined,
  high: number | null | undefined,
): { low: string; high: string } {
  const lowValue = parseFiniteNumber(low)
  const highValue = parseFiniteNumber(high)
  if (lowValue == null || highValue == null) {
    return { low: EM, high: EM }
  }
  let unit = selectNilDisplayUnit(benchmark ?? highValue)
  let lowStr = formatNilValueInUnit(lowValue, unit)
  let highStr = formatNilValueInUnit(highValue, unit)
  if (lowStr === highStr && lowValue !== highValue) {
    if (unit === 'M') {
      lowStr = formatNilValueInUnit(lowValue, 'K')
      highStr = formatNilValueInUnit(highValue, 'K')
    }
    if (lowStr === highStr) {
      lowStr = `$${Math.round(lowValue).toLocaleString('en-US')}`
      highStr = `$${Math.round(highValue).toLocaleString('en-US')}`
    }
  }
  return { low: lowStr, high: highStr }
}

export function formatNilRangeAligned(
  benchmark: number | null | undefined,
  low: number | null | undefined,
  high: number | null | undefined,
): string {
  const lowValue = parseFiniteNumber(low)
  const highValue = parseFiniteNumber(high)
  if (lowValue == null || highValue == null) {
    return `RECOMMENDED DEAL RANGE: ${EM} \u2013 ${EM}`
  }
  // Collapse to a single ESTIMATE label when the range is effectively flat
  // (within $250 difference). Mirrors backend `range_quality == "estimate"`
  // and prevents the "$17.9K – $17.9K" failure mode in CSC reports.
  if (Math.abs(highValue - lowValue) < 250) {
    const center = (lowValue + highValue) / 2
    return `ESTIMATE: ${formatNilValue(center)}`
  }
  const { low: lowStr, high: highStr } = formatNilBandEndpoints(benchmark, low, high)
  return `RECOMMENDED DEAL RANGE: ${lowStr} \u2013 ${highStr}`
}

export function isNilRangeEstimate(
  low: number | null | undefined,
  high: number | null | undefined,
): boolean {
  const lowValue = parseFiniteNumber(low)
  const highValue = parseFiniteNumber(high)
  if (lowValue == null || highValue == null) return false
  return Math.abs(highValue - lowValue) < 250
}

export { formatNilBandEndpoints }

export function formatNilRange(low: number | null | undefined, high: number | null | undefined): string {
  const lowValue = parseFiniteNumber(low)
  const highValue = parseFiniteNumber(high)
  const lowDisplay = lowValue == null ? EM : formatNilValue(lowValue)
  const highDisplay = highValue == null ? EM : formatNilValue(highValue)
  return `RECOMMENDED DEAL RANGE: ${lowDisplay} \u2013 ${highDisplay}`
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

/**
 * Format a driver supporting_metric value. Picks K/M for follower counts,
 * adds `$` for currency, percent for ratios, falls back to a localized int
 * for everything else. Returns `EM` when value is missing.
 */
export function formatDriverMetric(
  value: number | string | null | undefined,
  unit: string | null | undefined,
): string {
  if (value === null || value === undefined || value === '') return EM
  if (typeof value === 'string') return value
  if (!Number.isFinite(value)) return EM
  const u = (unit ?? '').toLowerCase()
  if (u === 'followers' || u === 'reach' || u === 'count') {
    if (Math.abs(value) >= 1_000_000) return `${(value / 1_000_000).toFixed(1)}M`
    if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(1)}K`
    return formatInteger(value)
  }
  if (u === '%') {
    return `${value.toFixed(1)}%`
  }
  if (u === '$') {
    return formatSignedMoneyDelta(value)
  }
  if (u === 'pts') {
    return `${value > 0 ? '+' : ''}${value.toFixed(1)}`
  }
  if (u === '/100' || u === 'score') {
    return value.toFixed(1)
  }
  if (u === '30d') {
    if (Math.abs(value) >= 1_000) return `${(value / 1_000).toFixed(1)}K`
    return formatInteger(value)
  }
  return formatInteger(value)
}

export { EM }
