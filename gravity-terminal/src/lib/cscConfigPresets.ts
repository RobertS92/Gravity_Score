import type { CscReportParams } from '../types/reports'

export type CscConfigMode = 'simple' | 'advanced'
export type CscMarketView = 'conservative' | 'balanced' | 'aggressive'
export type CscReportFocus =
  | 'overall'
  | 'brand'
  | 'commercial'
  | 'recruiting'

export interface CscSimpleConfig {
  marketView: CscMarketView
  reportFocus: CscReportFocus
  verifiedOnly: boolean
}

export const DEFAULT_SIMPLE_CONFIG: CscSimpleConfig = {
  marketView: 'balanced',
  reportFocus: 'overall',
  verifiedOnly: true,
}

const MARKET_VIEW_PARAMS: Record<CscMarketView, Partial<CscReportParams>> = {
  conservative: {
    confidence_min: 0.85,
    comparables_count: 10,
    csc_band_low_pct: 30,
    csc_band_high_pct: 70,
    verified_only: true,
  },
  balanced: {
    confidence_min: 0.75,
    comparables_count: 12,
    csc_band_low_pct: 25,
    csc_band_high_pct: 75,
    verified_only: true,
  },
  aggressive: {
    confidence_min: 0.65,
    comparables_count: 18,
    csc_band_low_pct: 15,
    csc_band_high_pct: 85,
    verified_only: false,
  },
}

function normalizeSportCode(code: string | null | undefined): string | undefined {
  if (!code) return undefined
  const upper = code.toUpperCase()
  // Backend canonical sport codes are CFB / NCAAB / NCAAW. The terminal
  // historically used `NCAAWB` for women's basketball; map it through.
  if (upper === 'NCAAWB') return 'NCAAW'
  return upper
}

/** Map Simple-mode choices to API report params (sport comes from athlete record). */
export function resolveCscReportParams(
  mode: CscConfigMode,
  simple: CscSimpleConfig,
  advanced: CscReportParams,
  athleteSport?: string | null,
): CscReportParams {
  if (mode === 'advanced') {
    // Migrate legacy `position` -> `position_group` (the backend reads
    // `position_group`; sending both keeps older agent payloads working).
    const positionGroup = advanced.position_group ?? advanced.position
    return {
      ...advanced,
      sport: normalizeSportCode(advanced.sport ?? athleteSport),
      position_group: positionGroup,
      position: positionGroup,
      report_focus: advanced.report_focus,
      market_view: advanced.market_view,
    }
  }
  const preset = MARKET_VIEW_PARAMS[simple.marketView]
  return {
    comparables_count: preset.comparables_count,
    confidence_min: preset.confidence_min,
    csc_band_low_pct: preset.csc_band_low_pct,
    csc_band_high_pct: preset.csc_band_high_pct,
    verified_only: simple.verifiedOnly,
    sport: normalizeSportCode(athleteSport),
    report_focus: simple.reportFocus,
    market_view: simple.marketView,
  }
}

export const REPORT_FOCUS_OPTIONS: { value: CscReportFocus; label: string }[] = [
  { value: 'overall', label: 'Overall Valuation' },
  { value: 'brand', label: 'Brand Potential' },
  { value: 'commercial', label: 'Commercial Readiness' },
  { value: 'recruiting', label: 'Recruiting / Transfer Outlook' },
]

export const MARKET_VIEW_OPTIONS: { value: CscMarketView; label: string; hint: string }[] = [
  {
    value: 'conservative',
    label: 'Conservative',
    hint: 'Tighter comparables, validated market data',
  },
  {
    value: 'balanced',
    label: 'Balanced',
    hint: 'Default middle-ground interpretation',
  },
  {
    value: 'aggressive',
    label: 'Aggressive',
    hint: 'Broader comparables, upside and momentum',
  },
]
