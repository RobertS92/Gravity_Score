import { useQuery } from '@tanstack/react-query'
import axios from 'axios'
import type { View } from '../hooks/useTerminalState'
import { AthleteProfile } from './views/AthleteProfile'
import { BrandMatch } from './views/BrandMatch'
import { Leaderboard } from './views/Leaderboard'
import { QueryResults } from './views/QueryResults'
import { ReportView } from './views/ReportView'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface MainPanelProps {
  view: View
  selectedAthlete: string | null
  queryResult: Record<string, unknown> | null
  onSelectAthlete: (id: string) => void
  onSetView: (v: View) => void
  isQuerying: boolean
}

export function MainPanel({
  view,
  selectedAthlete,
  queryResult,
  onSelectAthlete,
  onSetView,
  isQuerying,
}: MainPanelProps) {
  const { data: athleteData } = useQuery({
    queryKey: ['athlete', selectedAthlete],
    queryFn: () =>
      axios.get(`${API}/v1/athletes/${selectedAthlete}`).then((r) => r.data),
    enabled: !!selectedAthlete,
    staleTime: 1000 * 60 * 5,
  })

  if (isQuerying) {
    return (
      <div className="flex-1 flex items-center justify-center">
        <div className="text-center">
          <div className="text-[#6EA8FE] text-lg mb-2 animate-pulse">⟳ Agent running</div>
          <div className="text-[#4A5568] text-sm">
            {(queryResult?.query as string) || ''}
          </div>
        </div>
      </div>
    )
  }

  switch (view) {
    case 'leaderboard':
      return <Leaderboard onSelectAthlete={onSelectAthlete} />
    case 'athlete':
      return (
        <AthleteProfile data={athleteData} onSelectAthlete={onSelectAthlete} />
      )
    case 'query_results':
      return (
        <QueryResults
          result={queryResult}
          onSelectAthlete={(id) => {
            onSelectAthlete(id)
            onSetView('athlete')
          }}
        />
      )
    case 'report':
      return <ReportView result={queryResult} />
    case 'brand_match':
      return (
        <BrandMatch
          result={queryResult}
          onSelectAthlete={(id) => {
            onSelectAthlete(id)
            onSetView('athlete')
          }}
        />
      )
    case 'watchlist':
      return (
        <div className="flex-1 p-4 text-sm text-[#94A3B8]">
          Watchlist view — connect authenticated user UUID to{' '}
          <code className="text-[#6EA8FE]">/v1/watchlist</code>.
        </div>
      )
    case 'alerts':
      return (
        <div className="flex-1 p-4 text-sm text-[#94A3B8]">
          Alerts view — use <code className="text-[#6EA8FE]">/v1/alerts</code> with user id.
        </div>
      )
    default:
      return <Leaderboard onSelectAthlete={onSelectAthlete} />
  }
}
