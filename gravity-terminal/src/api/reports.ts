import type {
  BrandMatchBrief,
  BrandMatchDiagnostics,
  BrandMatchResponse,
  BrandMatchResult,
  CscReportJson,
  CscReportParams,
} from '../types/reports'
import { apiPost } from './client'

export function postCscReport(athleteId: string, params: CscReportParams) {
  return apiPost<CscReportJson>(`reports/csc`, { athlete_id: athleteId, ...params })
}

/** Normalize legacy array responses and the new `{ matches, diagnostics }` shape. */
export async function postBrandMatch(brief: BrandMatchBrief): Promise<BrandMatchResponse> {
  const raw = await apiPost<BrandMatchResult[] | BrandMatchResponse>(`reports/brand-match`, brief)
  if (Array.isArray(raw)) {
    return { matches: raw, diagnostics: undefined }
  }
  const matches = Array.isArray(raw?.matches) ? raw.matches : []
  const diagnostics = raw?.diagnostics as BrandMatchDiagnostics | undefined
  return { matches, diagnostics }
}
