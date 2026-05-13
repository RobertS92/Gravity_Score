import type { CscReportComparablesRow } from '../types/reports'

type OptionGroup = {
  label: string
  options: readonly string[]
}

export const DEAL_STRUCTURE_FALLBACK = 'Structure pending verification'
export const SOURCE_FALLBACK = 'Source pending verification'

export const DEAL_STRUCTURE_GROUPS: readonly OptionGroup[] = [
  {
    label: 'Cash-Focused',
    options: [
      'Cash / Flat Fee',
      'Cash + Appearances',
      'Cash + Performance Bonus',
      'Milestone-Based',
      'Retainer',
    ],
  },
  {
    label: 'Content & Ambassador',
    options: ['Content Package', 'Social Campaign', 'Event Appearance', 'Brand Ambassador Program'],
  },
  {
    label: 'Equity & Revenue Share',
    options: ['Product / In-Kind', 'Revenue Share / Affiliate', 'Equity / Options'],
  },
  {
    label: 'General',
    options: ['Hybrid', 'Other / Unspecified', DEAL_STRUCTURE_FALLBACK],
  },
] as const

export const SOURCE_GROUPS: readonly OptionGroup[] = [
  {
    label: 'Verified Data Sources',
    options: ['Direct Verification', 'On3', 'Opendorse', 'INFLCR', 'Teamworks', 'Marketplace Platform'],
  },
  {
    label: 'Public Reporting',
    options: ['School Disclosure', 'Collective Announcement', 'Press Report', 'Social Post'],
  },
  {
    label: 'Internal Assessment',
    options: ['Analyst Estimate', 'Model Estimate', SOURCE_FALLBACK],
  },
] as const

function sanitizeText(value: string | null | undefined, fallback: string): string {
  const cleaned = (value ?? '').trim()
  return cleaned.length > 0 ? cleaned : fallback
}

function normalizeComparisonText(
  value: string | null | undefined,
  fallback: string,
  synonyms: Record<string, string>,
): string {
  const cleaned = sanitizeText(value, fallback)
  return synonyms[cleaned.toLowerCase()] ?? cleaned
}

const DEAL_STRUCTURE_SYNONYMS: Record<string, string> = {
  hybrid: 'Hybrid',
  'cash + appearances': 'Cash + Appearances',
  'cash+appearances': 'Cash + Appearances',
  'cash + performance': 'Cash + Performance Bonus',
  'cash + performance bonus': 'Cash + Performance Bonus',
  'fixed fee': 'Cash / Flat Fee',
  'flat fee': 'Cash / Flat Fee',
  fixed: 'Cash / Flat Fee',
  performance: 'Milestone-Based',
  milestone: 'Milestone-Based',
  milestones: 'Milestone-Based',
  'product only': 'Product / In-Kind',
  'in kind': 'Product / In-Kind',
  'in-kind': 'Product / In-Kind',
  equity: 'Equity / Options',
  affiliate: 'Revenue Share / Affiliate',
  'revenue share': 'Revenue Share / Affiliate',
  'revenue-share': 'Revenue Share / Affiliate',
  'event appearance': 'Event Appearance',
  appearances: 'Event Appearance',
  'source pending verification': DEAL_STRUCTURE_FALLBACK,
}

const SOURCE_SYNONYMS: Record<string, string> = {
  'verified deal': 'Direct Verification',
  verified: 'Direct Verification',
  'on3 pro': 'On3',
  on3: 'On3',
  'model estimate': 'Model Estimate',
  model: 'Model Estimate',
  'source unavailable': SOURCE_FALLBACK,
  unavailable: SOURCE_FALLBACK,
  'pending verification': SOURCE_FALLBACK,
}

function toFiniteNumber(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  if (typeof value === 'string') {
    const trimmed = value.trim()
    if (!trimmed) return null
    const parsed = Number(trimmed)
    return Number.isFinite(parsed) ? parsed : null
  }
  return null
}

function midpoint(low: number | null, high: number | null): number | null {
  if (low == null || high == null) return null
  return (low + high) / 2
}

function resolveComparableNilEstimate(row: CscReportComparablesRow): number | null {
  const raw = row as CscReportComparablesRow & Record<string, unknown>
  const p10 = toFiniteNumber(raw.dollar_p10_usd)
  const p50 = toFiniteNumber(raw.dollar_p50_usd)
  const p90 = toFiniteNumber(raw.dollar_p90_usd)
  const mid = midpoint(p10, p90)
  return (
    toFiniteNumber(raw.deal_value)
    ?? toFiniteNumber(raw.nil_valuation_consensus)
    ?? toFiniteNumber(raw.nil_estimate)
    ?? p50
    ?? mid
    ?? toFiniteNumber(raw.nil_valuation_raw)
    ?? toFiniteNumber(raw.nil_value_raw)
    ?? toFiniteNumber(raw.nil_value_usd)
  )
}

export function normalizeComparableConfidence(value: unknown): number | null {
  if (typeof value !== 'number' || !Number.isFinite(value)) return null
  if (value <= 0) return 0
  let normalized = value
  while (normalized > 1) {
    normalized /= 100
  }
  if (!Number.isFinite(normalized)) return null
  return Math.min(1, Math.max(0, normalized))
}

export function formatComparableConfidence(value: unknown): string {
  const normalized = normalizeComparableConfidence(value)
  if (normalized == null) return '\u2014'
  return `${Math.round(normalized * 100)}%`
}

export function normalizeComparableRow(row: CscReportComparablesRow): CscReportComparablesRow {
  return {
    ...row,
    nil_valuation_consensus: resolveComparableNilEstimate(row),
    deal_structure: normalizeComparisonText(
      typeof row.deal_structure === 'string' ? row.deal_structure : null,
      DEAL_STRUCTURE_FALLBACK,
      DEAL_STRUCTURE_SYNONYMS,
    ),
    verified_source: normalizeComparisonText(
      typeof row.verified_source === 'string' ? row.verified_source : null,
      SOURCE_FALLBACK,
      SOURCE_SYNONYMS,
    ),
    confidence: normalizeComparableConfidence(row.confidence),
  }
}

export function normalizeComparableRows(rows: CscReportComparablesRow[] | undefined): CscReportComparablesRow[] {
  return (rows ?? []).map(normalizeComparableRow)
}

export function withLegacyOption(
  groups: readonly OptionGroup[],
  value: string | null | undefined,
): { groups: readonly OptionGroup[]; value: string } {
  const selected = sanitizeText(value, 'Other / Unspecified')
  const isKnown = groups.some((group) => group.options.includes(selected))
  if (isKnown) return { groups, value: selected }
  return {
    value: selected,
    groups: [{ label: 'Legacy / Imported', options: [selected] }, ...groups],
  }
}
