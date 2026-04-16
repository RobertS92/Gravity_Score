import type { BrandMatchBrief, BrandMatchResult, CscReportJson, CscReportParams } from '../types/reports'
import { apiPost } from './client'

export function postCscReport(athleteId: string, params: CscReportParams) {
  return apiPost<CscReportJson>(`reports/csc`, { athlete_id: athleteId, ...params })
}

export function postBrandMatch(brief: BrandMatchBrief) {
  return apiPost<BrandMatchResult[]>(`reports/brand-match`, brief)
}
