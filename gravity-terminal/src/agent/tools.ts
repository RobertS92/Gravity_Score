import { getAthlete, getComparables, getScoreHistory, searchAthletes } from '../api/athletes'
import { getMarketScan } from '../api/market'
import { postBrandMatch, postCscReport } from '../api/reports'
import { getWatchlist } from '../api/watchlist'
import type { BrandMatchBrief } from '../types/reports'
import { mockSearchAthleteNames } from '../mocks/handlers'
import { isMockMode } from '../api/client'
import { getTerminalUserId } from '../stores/authStore'

export const TOOL_DEFINITIONS = [
  {
    name: 'get_athlete_profile',
    description: 'Load full profile for an athlete_id',
    input_schema: {
      type: 'object',
      properties: { athlete_id: { type: 'string' } },
      required: ['athlete_id'],
    },
  },
  {
    name: 'search_athletes',
    description: 'Search athletes by name fragment; returns ids',
    input_schema: {
      type: 'object',
      properties: { query: { type: 'string' } },
      required: ['query'],
    },
  },
  {
    name: 'get_comparables',
    description: 'Get comparables for athlete',
    input_schema: {
      type: 'object',
      properties: { athlete_id: { type: 'string' } },
      required: ['athlete_id'],
    },
  },
  {
    name: 'generate_csc_report',
    description: 'Generate CSC structured report JSON',
    input_schema: {
      type: 'object',
      properties: {
        athlete_id: { type: 'string' },
        comparables_count: { type: 'number' },
      },
      required: ['athlete_id'],
    },
  },
  {
    name: 'run_brand_match',
    description: 'Run brand match with brief',
    input_schema: {
      type: 'object',
      properties: {
        budget: { type: 'number' },
        category: { type: 'string' },
      },
      required: ['budget', 'category'],
    },
  },
  {
    name: 'get_market_scan',
    description: 'Market scan table — find athletes by sport/position/conference/score',
    input_schema: {
      type: 'object',
      properties: {
        sport: { type: 'string' },
        position: { type: 'string' },
        conference: { type: 'string' },
        min_score: { type: 'number' },
        max_risk: { type: 'number' },
      },
    },
  },
  {
    name: 'get_score_history',
    description: 'Weekly Gravity Score and NIL valuation history for an athlete',
    input_schema: {
      type: 'object',
      properties: {
        athlete_id: { type: 'string' },
        days: { type: 'number', description: 'How many days of history (default 90)' },
      },
      required: ['athlete_id'],
    },
  },
  {
    name: 'get_watchlist_summary',
    description: "Return all watchlisted athletes with current scores and 30-day deltas",
    input_schema: {
      type: 'object',
      properties: {},
    },
  },
] as const

export async function runTool(name: string, input: Record<string, unknown>): Promise<string> {
  try {
    switch (name) {
      case 'get_athlete_profile': {
        const id = String(input.athlete_id ?? '')
        const a = await getAthlete(id)
        return JSON.stringify(a)
      }
      case 'search_athletes': {
        const q = String(input.query ?? '')
        if (isMockMode()) {
          const hits = mockSearchAthleteNames(q).map((a) => ({ athlete_id: a.athlete_id, name: a.name }))
          return JSON.stringify(hits)
        }
        try {
          const hits = await searchAthletes(q)
          return JSON.stringify(hits)
        } catch (e) {
          return JSON.stringify({ error: e instanceof Error ? e.message : 'search_failed' })
        }
      }
      case 'get_comparables': {
        const id = String(input.athlete_id ?? '')
        const c = await getComparables(id)
        return JSON.stringify(c)
      }
      case 'generate_csc_report': {
        const athlete_id = String(input.athlete_id ?? '')
        const comparables_count = typeof input.comparables_count === 'number' ? input.comparables_count : 12
        const r = await postCscReport(athlete_id, { comparables_count })
        return JSON.stringify(r)
      }
      case 'run_brand_match': {
        const brief: BrandMatchBrief = {
          budget: Number(input.budget ?? 0),
          category: String(input.category ?? 'other'),
          geography: [],
          audience: [],
          risk_tolerance: 0.5,
          max_transfer_risk: false,
          authenticity_weight: 0.5,
        }
        const r = await postBrandMatch(brief)
        return JSON.stringify(r)
      }
      case 'get_market_scan': {
        const r = await getMarketScan({
          sport: input.sport as string | undefined,
          position: input.position as string | undefined,
          conference: input.conference as string | undefined,
          min_score: input.min_score as number | undefined,
        })
        return JSON.stringify(r)
      }
      case 'get_score_history': {
        const id = String(input.athlete_id ?? '')
        const history = await getScoreHistory(id)
        return JSON.stringify(history)
      }
      case 'get_watchlist_summary': {
        const userId = getTerminalUserId()
        if (!userId) return JSON.stringify({ athletes: [] })
        const wl = await getWatchlist(userId)
        return JSON.stringify(wl)
      }
      default:
        return JSON.stringify({ error: 'unknown_tool' })
    }
  } catch (e) {
    return JSON.stringify({ error: e instanceof Error ? e.message : 'tool_failed' })
  }
}
