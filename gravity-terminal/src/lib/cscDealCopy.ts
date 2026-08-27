import type { CscDetailSection, CscReportMetadata, DealScope } from '../types/reports'

export interface DealScopeCopy {
  menuLabel: string
  blurb: string
}

export type ConfidenceTier = 'high' | 'moderate' | 'low' | 'uncalibrated'

export const EVIDENCE_CALIBRATION_THRESHOLD = 100
export const MIN_COHORT_FOR_TIER_BADGE = 3
export const PDF_PLANNING_BANNER = 'DRAFT — PLANNING ESTIMATE, LOW CONFIDENCE'

export const DEAL_SCOPE_COPY: Record<DealScope, DealScopeCopy> = {
  standard_activation: {
    menuLabel: 'One campaign (4–6 weeks)',
    blurb: 'A single brand activation — posts, appearances, or usage rights over about a month.',
  },
  season_partnership: {
    menuLabel: 'Season-long partnership',
    blurb: 'A multi-month individual partnership across one college season.',
  },
  collective_package: {
    menuLabel: 'Collective / roster support',
    blurb: 'A collective or roster-support package. This is not a brand activation.',
  },
  group_licensing: {
    menuLabel: 'Group licensing share',
    blurb: "This athlete's allocation from a multi-athlete licensing program.",
  },
  revenue_sharing: {
    menuLabel: 'Revenue-sharing allocation',
    blurb: "This athlete's allocation from institutional revenue sharing.",
  },
}

export function dealScopeCopy(scope: string | null | undefined): DealScopeCopy {
  if (scope && scope in DEAL_SCOPE_COPY) {
    return DEAL_SCOPE_COPY[scope as DealScope]
  }
  return DEAL_SCOPE_COPY.standard_activation
}

export function classifyDealConfidence(raw: string | null | undefined): ConfidenceTier {
  const token = (raw ?? '').trim().toLowerCase()
  if (token.startsWith('high')) return 'high'
  if (token.startsWith('moderate') || token.startsWith('medium')) return 'moderate'
  if (token.startsWith('low')) return 'low'
  return 'uncalibrated'
}

export function dealConfidenceCopy(raw: string | null | undefined): {
  title: string
  detail: string
  tier: ConfidenceTier
} {
  const tier = classifyDealConfidence(raw)
  if (tier === 'high') {
    return { title: 'High confidence', detail: 'Closed-deal history supports this range.', tier }
  }
  if (tier === 'moderate') {
    return {
      title: 'Moderate confidence — use the range, not a point',
      detail: 'Use the range, not a single point, when you negotiate.',
      tier,
    }
  }
  if (tier === 'low') {
    return {
      title: 'Low confidence — directional only',
      detail: 'Treat this as directional. Widen the conversation around the band.',
      tier,
    }
  }
  return {
    title: 'Planning estimate — not yet backed by closed deals',
    detail: 'Not enough closed deals in this category yet to treat this as a locked market price.',
    tier,
  }
}

export function dealEvidenceCopy(
  qualified: number | null | undefined,
  readiness: string | null | undefined,
): { title: string; detail: string; count: number; threshold: number } {
  const n =
    typeof qualified === 'number' && Number.isFinite(qualified) ? Math.max(0, Math.round(qualified)) : 0
  const threshold = EVIDENCE_CALIBRATION_THRESHOLD
  const countClause = `${n} of ${threshold} qualified transactions`
  const token = (readiness ?? 'insufficient_data').trim().toLowerCase()
  if (token === 'production') {
    return {
      title: 'Calibrated',
      detail: `${countClause} inform the range.`,
      count: n,
      threshold,
    }
  }
  if (token === 'pilot') {
    return {
      title: 'Early evidence',
      detail: `${countClause} — enough to start calibrating, not enough to lock.`,
      count: n,
      threshold,
    }
  }
  if (n > 0) {
    return {
      title: 'Limited evidence',
      detail: `${countClause} on file. Need ${threshold} in this category before the range is calibrated.`,
      count: n,
      threshold,
    }
  }
  return {
    title: 'Not yet calibrated',
    detail: `${countClause} on file. The band is a planning prior, not a measured market.`,
    count: n,
    threshold,
  }
}

export function isPlanningEstimateExport(
  confidence: string | null | undefined,
  qualifiedTransactions: number | null | undefined,
): boolean {
  const tier = classifyDealConfidence(confidence)
  const n =
    typeof qualifiedTransactions === 'number' && Number.isFinite(qualifiedTransactions)
      ? qualifiedTransactions
      : 0
  return tier === 'uncalibrated' || tier === 'low' || n < EVIDENCE_CALIBRATION_THRESHOLD
}

export function shouldShowTierBadge(args: {
  cohortSize?: number | null
  comparableState?: string | null
  lowCohortData?: boolean | null
}): boolean {
  if (args.lowCohortData === true) return false
  if (args.comparableState === 'none') return false
  const n = args.cohortSize
  if (n == null || !Number.isFinite(n) || n < MIN_COHORT_FOR_TIER_BADGE) return false
  return true
}

export function titleCaseChip(raw: string): string {
  const small = new Set(['vs', 'of', 'the', 'a', 'an'])
  return raw
    .trim()
    .split(/\s+/)
    .map((word, idx) => {
      const lower = word.toLowerCase()
      if (idx > 0 && small.has(lower)) return lower
      return lower.charAt(0).toUpperCase() + lower.slice(1)
    })
    .join(' ')
}

export function fallbackTakeaway(
  athleteName: string,
  yearly: string,
  offerLow: string,
  offerHigh: string,
): string {
  return (
    `${athleteName}'s yearly market value is ${yearly}. ` +
    `Suggested offer for one campaign: ${offerLow} to ${offerHigh}.`
  )
}

const YEARLY_OFFER_CONFLATION = [
  /\bbrackets?\b/i,
  /\bband around\b/i,
  /\bcontains the (yearly|annual|benchmark)\b/i,
  /\bone (single )?figure\b/i,
  /\bsame (number|figure|value) as\b/i,
]

export function yearlyOfferConflationReason(text: string): string | null {
  const sample = (text ?? '').trim()
  if (!sample) return null
  for (const pattern of YEARLY_OFFER_CONFLATION) {
    if (pattern.test(sample)) return `yearly_offer_conflation:${pattern.source}`
  }
  return null
}

const RISK_ELEVATING = /\b(elevated|defensive deal construction|shorter terms|high risk)\b/i
const HIGH_CONTRADICTION = /\b(weak|lags?\b|below peers|thin support)\b/i

export function driverNarrativeConflictsBadge(label: string, signal: string, explanation: string): boolean {
  const grade = (signal ?? '').trim().toLowerCase()
  const prose = explanation ?? ''
  if (label === 'Risk' && grade === 'low' && RISK_ELEVATING.test(prose)) return true
  if (grade === 'high' && HIGH_CONTRADICTION.test(prose)) return true
  return false
}

export function modelAuditBullets(
  metadata: CscReportMetadata | null | undefined,
  detail: CscDetailSection | null | undefined,
): string[] {
  const fromBlocks = detail?.blocks?.methodology?.components ?? []
  if (fromBlocks.length >= 4 && fromBlocks[0]?.toLowerCase().startsWith('model version')) {
    return fromBlocks.slice(0, 4)
  }
  const version = metadata?.model_version || 'unspecified'
  const status = metadata?.model_status || 'unknown'
  const shapRows = detail?.blocks?.shap_attribution?.rows ?? []
  const shapLine = shapRows.length
    ? shapRows
        .slice(0, 5)
        .map((row) => `${row.feature} (${row.contribution >= 0 ? '+' : ''}${row.contribution.toFixed(2)})`)
        .join(', ')
    : detail?.shap_attribution || 'SHAP pending latest explainable model output.'
  const provenance = detail?.blocks?.provenance
  const populated = provenance?.feature_populated
  const total = provenance?.feature_total
  const featureLine =
    populated != null && total != null
      ? `Feature vector: ${populated}/${total} populated`
      : 'Feature vector: completeness not yet recorded on this preview.'
  const scoredAt = provenance?.scored_at || 'unknown'
  return [
    `Model version: ${version} (${status})`,
    `Top SHAP drivers: ${shapLine}`,
    featureLine,
    `Last scored: ${scoredAt}`,
  ]
}
