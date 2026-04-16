import { searchAthletes } from '../api/athletes'
import { mockSearchAthleteNames } from '../mocks/handlers'
import { isMockMode } from '../api/client'

export type ParsedCommand =
  | { kind: 'score'; name: string }
  | { kind: 'watchlist_add'; name: string }
  | { kind: 'watchlist_remove'; name: string }
  | { kind: 'csc_report' }
  | { kind: 'brand_match'; rest: string }
  | { kind: 'compare'; names: string[] }
  | { kind: 'scan'; position?: string; conference?: string }
  | { kind: 'scope_reject'; league: string }
  | { kind: 'none' }

const OOS = /NFL|NBA|WNBA|MLB|MLS/i

export function parseStructuredCommand(raw: string): ParsedCommand {
  const line = raw.trim()
  if (!line) return { kind: 'none' }

  if (OOS.test(line) && !line.toLowerCase().includes('ncaa') && !line.toLowerCase().includes('cfb')) {
    const m = line.match(OOS)
    return { kind: 'scope_reject', league: m?.[0] ?? 'PRO' }
  }

  const scoreM = line.match(/^score\s+--athlete\s+"([^"]+)"/i)
  if (scoreM) return { kind: 'score', name: scoreM[1] }

  const addM = line.match(/^watchlist\s+--add\s+"([^"]+)"/i)
  if (addM) return { kind: 'watchlist_add', name: addM[1] }

  const remM = line.match(/^watchlist\s+--remove\s+"([^"]+)"/i)
  if (remM) return { kind: 'watchlist_remove', name: remM[1] }

  if (/^csc\s+--report/i.test(line)) return { kind: 'csc_report' }

  const brandM = line.match(/^brand\s+--match\s+(.+)/i)
  if (brandM) return { kind: 'brand_match', rest: brandM[1].trim() }

  const cmpM = line.match(/^compare\s+(.+)/i)
  if (cmpM) {
    const inner = cmpM[1]
    const names = [...inner.matchAll(/"([^"]+)"/g)].map((x) => x[1])
    if (names.length >= 2) return { kind: 'compare', names }
  }

  const scanM = line.match(/^scan(?:\s+(.+))?$/i)
  if (scanM) {
    const rest = scanM[1] ?? ''
    const pos = rest.match(/--position\s+(\S+)/i)?.[1]
    const conf = rest.match(/--conference\s+(\S+)/i)?.[1]
    return { kind: 'scan', position: pos, conference: conf }
  }

  return { kind: 'none' }
}

export async function resolveAthleteByName(name: string): Promise<string | null> {
  const q = name.trim()
  if (!q) return null
  if (isMockMode()) {
    const hits = mockSearchAthleteNames(q)
    const exact = hits.find((a) => a.name.toLowerCase() === q.toLowerCase())
    return (exact ?? hits[0])?.athlete_id ?? null
  }
  try {
    const hits = await searchAthletes(q)
    const exact = hits.find((a) => a.name.toLowerCase() === q.toLowerCase())
    return (exact ?? hits[0])?.athlete_id ?? null
  } catch {
    return null
  }
}
