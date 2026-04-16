import type { NavigateFunction } from 'react-router-dom'
import type { CscReportJson } from '../types/reports'
import { useAthleteStore } from '../stores/athleteStore'
import { useUiStore } from '../stores/uiStore'

function isCscReport(o: unknown): o is CscReportJson {
  if (!o || typeof o !== 'object') return false
  const x = o as Record<string, unknown>
  return typeof x.executive_summary === 'string' && typeof x.gravity_score_table === 'string'
}

function normalizeCscReport(o: CscReportJson): CscReportJson {
  return {
    executive_summary: o.executive_summary,
    gravity_score_table: o.gravity_score_table,
    comparables_analysis: Array.isArray(o.comparables_analysis) ? o.comparables_analysis : [],
    nil_range_note: typeof o.nil_range_note === 'string' ? o.nil_range_note : '',
    shap_narrative: typeof o.shap_narrative === 'string' ? o.shap_narrative : '',
    risk_assessment: typeof o.risk_assessment === 'string' ? o.risk_assessment : '',
    methodology: typeof o.methodology === 'string' ? o.methodology : '',
  }
}

function extractJsonObject(text: string): string | null {
  const t = text.trim()
  const codeBlock = t.match(/```(?:json)?\s*([\s\S]*?)```/i)
  if (codeBlock) {
    const inner = codeBlock[1]?.trim()
    if (inner?.startsWith('{')) return inner
  }
  const i = t.indexOf('{')
  if (i < 0) return null
  let depth = 0
  for (let j = i; j < t.length; j++) {
    const c = t[j]
    if (c === '{') depth++
    else if (c === '}') {
      depth--
      if (depth === 0) return t.slice(i, j + 1)
    }
  }
  return null
}

/**
 * If the model returned JSON for a CSC report or athlete id / profile, apply it and navigate.
 * Returns true when navigation was triggered (response may still be shown in the output panel).
 */
export async function tryApplyAgentResponseText(text: string, navigate: NavigateFunction): Promise<boolean> {
  const blob = extractJsonObject(text)
  if (!blob) return false
  let o: unknown
  try {
    o = JSON.parse(blob)
  } catch {
    return false
  }
  if (isCscReport(o)) {
    useUiStore.getState().setCscLockedFromAgent(true)
    navigate('/csc', { state: { agentCscReport: normalizeCscReport(o) } })
    return true
  }
  if (typeof o === 'object' && o !== null && 'athlete_id' in o) {
    const aid = String((o as { athlete_id: unknown }).athlete_id).trim()
    if (aid) {
      await useAthleteStore.getState().setActiveAthlete(aid)
      navigate('/')
      return true
    }
  }
  return false
}
