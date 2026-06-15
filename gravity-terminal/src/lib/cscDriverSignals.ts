import { formatInteger, formatScore } from './formatters'
import type { AthleteRecord } from '../types/athlete'
import type { CscKeyValueDriver, CscSignalLevel } from '../types/reports'

function fmtFollowers(n: number | null | undefined): string {
  if (n == null) return 'N/A'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${Math.round(n / 1_000)}K`
  return String(n)
}

function levelFromScore(value: number | null | undefined, invert = false): CscSignalLevel {
  if (value == null || Number.isNaN(value)) return 'Moderate'
  const adjusted = invert ? 100 - value : value
  if (adjusted >= 66) return 'High'
  if (adjusted >= 40) return 'Moderate'
  return 'Low'
}

function newsVisibilityLabel(mentions: number | null | undefined): string {
  if (mentions == null) return 'N/A'
  if (mentions >= 20) return 'High'
  if (mentions >= 5) return 'Emerging'
  return 'Limited'
}

function wikiActivityLabel(views: number | null | undefined): string {
  if (views == null) return 'N/A'
  if (views >= 50_000) return 'High'
  if (views >= 10_000) return 'Moderate'
  return 'Emerging'
}

function trendsLabel(score: number | null | undefined): string {
  if (score == null) return 'N/A'
  if (score >= 60) return 'Rising'
  if (score >= 35) return 'Stable'
  return 'Limited'
}

function commercialReadinessScore(athlete: AthleteRecord): number | null {
  const parts: number[] = []
  if (athlete.brand_score != null) parts.push(athlete.brand_score)
  if (athlete.instagram_engagement_rate != null) {
    parts.push(Math.min(100, athlete.instagram_engagement_rate * 10))
  }
  if (athlete.verified_deals_count != null && athlete.verified_deals_count > 0) {
    parts.push(Math.min(100, 40 + athlete.verified_deals_count * 8))
  }
  if (!parts.length) return null
  return parts.reduce((a, b) => a + b, 0) / parts.length
}

export function supportingSignalsForDriver(
  label: string,
  athlete: AthleteRecord,
): { label: string; value: string }[] {
  switch (label) {
    case 'Brand Strength':
      return [
        { label: 'Instagram', value: fmtFollowers(athlete.instagram_followers) },
        { label: 'TikTok', value: fmtFollowers(athlete.tiktok_followers) },
        { label: 'X', value: fmtFollowers(athlete.twitter_followers) },
        {
          label: 'Instagram Engagement Rate',
          value:
            athlete.instagram_engagement_rate != null
              ? `${formatScore(athlete.instagram_engagement_rate)}%`
              : 'N/A',
        },
      ]
    case 'Exposure':
      return [
        { label: 'News Visibility', value: newsVisibilityLabel(athlete.news_mentions_30d) },
        { label: 'Wikipedia Activity', value: wikiActivityLabel(athlete.wikipedia_page_views_30d) },
        { label: 'Search Interest', value: trendsLabel(athlete.google_trends_score) },
      ]
    case 'Market Proof':
      return [
        {
          label: 'Conference',
          value: athlete.conference ?? 'N/A',
        },
        { label: 'Position', value: athlete.position ?? 'N/A' },
        {
          label: 'Verified deals',
          value: formatInteger(athlete.verified_deals_count),
        },
        {
          label: 'Proof score',
          value: formatScore(athlete.proof_score),
        },
      ]
    case 'Momentum':
      return [
        { label: 'Velocity score', value: formatScore(athlete.velocity_score) },
        {
          label: '30d NIL delta',
          value:
            athlete.nil_valuation_delta_30d != null
              ? `${athlete.nil_valuation_delta_30d >= 0 ? '+' : ''}${fmtFollowers(Math.abs(athlete.nil_valuation_delta_30d))}`
              : 'N/A',
        },
        {
          label: '30d Gravity delta',
          value:
            athlete.gravity_delta_30d != null
              ? `${athlete.gravity_delta_30d >= 0 ? '+' : ''}${formatScore(athlete.gravity_delta_30d)}`
              : 'N/A',
        },
      ]
    case 'Commercial Readiness':
      return [
        {
          label: 'Combined reach',
          value: fmtFollowers(athlete.social_combined_reach),
        },
        {
          label: 'Engagement rate (IG)',
          value:
            athlete.instagram_engagement_rate != null
              ? `${formatScore(athlete.instagram_engagement_rate)}%`
              : 'N/A',
        },
        { label: 'Deals on file', value: formatInteger(athlete.verified_deals_count) },
        {
          label: 'Data quality',
          value:
            athlete.data_quality_score != null
              ? `${Math.round(athlete.data_quality_score * 100)}%`
              : 'N/A',
        },
      ]
    case 'Risk':
      return [
        { label: 'Risk score', value: formatScore(athlete.risk_score) },
        {
          label: 'Roster status',
          value: athlete.roster_inactive ? 'Inactive' : 'Active',
        },
        {
          label: 'Model confidence',
          value: athlete.dollar_confidence?.dollar_confidence_label ?? 'N/A',
        },
      ]
    default:
      return []
  }
}

function defaultDriversFromAthlete(athlete: AthleteRecord): CscKeyValueDriver[] {
  const commercial = commercialReadinessScore(athlete)
  return [
    {
      label: 'Brand Strength',
      signal: levelFromScore(athlete.brand_score),
      explanation: '',
      supporting_signals: supportingSignalsForDriver('Brand Strength', athlete),
    },
    {
      label: 'Market Proof',
      signal: levelFromScore(athlete.proof_score),
      explanation: '',
      supporting_signals: supportingSignalsForDriver('Market Proof', athlete),
    },
    {
      label: 'Exposure',
      signal: levelFromScore(athlete.proximity_score),
      explanation: '',
      supporting_signals: supportingSignalsForDriver('Exposure', athlete),
    },
    {
      label: 'Momentum',
      signal: levelFromScore(athlete.velocity_score),
      explanation: '',
      supporting_signals: supportingSignalsForDriver('Momentum', athlete),
    },
    {
      label: 'Commercial Readiness',
      signal: levelFromScore(commercial),
      explanation: '',
      supporting_signals: supportingSignalsForDriver('Commercial Readiness', athlete),
    },
    {
      label: 'Risk',
      signal: levelFromScore(athlete.risk_score, true),
      explanation: '',
      supporting_signals: supportingSignalsForDriver('Risk', athlete),
    },
  ]
}

const DRIVER_ORDER = [
  'Brand Strength',
  'Market Proof',
  'Exposure',
  'Momentum',
  'Commercial Readiness',
  'Risk',
]

/** Merge API drivers with athlete-backed supporting signals; fill missing drivers. */
export function enrichKeyValueDrivers(
  drivers: CscKeyValueDriver[] | undefined,
  athlete: AthleteRecord | null,
): CscKeyValueDriver[] {
  if (!athlete) return drivers ?? []
  const defaults = defaultDriversFromAthlete(athlete)
  const byLabel = new Map<string, CscKeyValueDriver>()
  for (const d of drivers ?? []) {
    byLabel.set(d.label, {
      ...d,
      supporting_signals:
        d.supporting_signals?.length
          ? d.supporting_signals
          : supportingSignalsForDriver(d.label, athlete),
    })
  }
  for (const d of defaults) {
    if (!byLabel.has(d.label)) byLabel.set(d.label, d)
  }
  return DRIVER_ORDER.map((label) => byLabel.get(label)).filter((d): d is CscKeyValueDriver => !!d)
}
