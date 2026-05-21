/**
 * Pure helpers that map CSC report metadata strings to UI tag tokens.
 *
 * Kept in their own module so they can be unit-tested without a DOM.
 * The React layer maps the returned token to its CSS-module class name.
 */

export type TierTagToken = 'top' | 'mid' | 'developing' | 'emerging' | null

export type ConfidenceTagToken = 'high' | 'moderate' | 'low' | null

export type ConferenceTierToken =
  | 'power_5'
  | 'power_4'
  | 'power_6'
  | 'group_of_5'
  | 'fcs'
  | 'mid_major'
  | 'other'

export function classifyTierTag(tier: string | null | undefined): TierTagToken {
  if (!tier) return null
  const normalized = tier.replace(/\*+$/, '').trim().toLowerCase()
  if (normalized.startsWith('top')) return 'top'
  if (normalized.startsWith('mid')) return 'mid'
  if (normalized.startsWith('emerging')) return 'emerging'
  if (normalized.startsWith('developing')) return 'developing'
  return null
}

export function classifyConfidenceTag(confidence: string | null | undefined): ConfidenceTagToken {
  if (!confidence) return null
  const normalized = confidence.trim().toLowerCase()
  if (normalized.startsWith('high')) return 'high'
  if (normalized.startsWith('moderate')) return 'moderate'
  if (normalized.startsWith('low')) return 'low'
  return null
}

export function classifyConferenceTier(tier: string | null | undefined): ConferenceTierToken | null {
  if (!tier) return null
  const normalized = tier.trim().toLowerCase() as ConferenceTierToken
  const valid: ConferenceTierToken[] = [
    'power_5',
    'power_4',
    'power_6',
    'group_of_5',
    'fcs',
    'mid_major',
    'other',
  ]
  return valid.includes(normalized) ? normalized : null
}

export function conferenceTierDisplayLabel(tier: string | null | undefined): string | null {
  const token = classifyConferenceTier(tier)
  if (!token) return null
  const labels: Record<ConferenceTierToken, string> = {
    power_5: 'Power 5',
    power_4: 'Power 4',
    power_6: 'Power 6',
    group_of_5: 'Group of 5',
    fcs: 'FCS',
    mid_major: 'Mid-Major',
    other: 'Other',
  }
  return labels[token]
}

/**
 * True when the cohort fit warrants suppressing percentile-style displays
 * (per spec — "exceeds peer cohort distribution" copy is shown instead).
 */
export function shouldSuppressPercentile(cohortFit: string | null | undefined): boolean {
  if (!cohortFit) return false
  return cohortFit.trim().toLowerCase() === 'poor'
}
