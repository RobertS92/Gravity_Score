import axios from 'axios'
import { useQuery } from '@tanstack/react-query'
import { useCallback, useEffect, useState } from 'react'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

export type View =
  | 'leaderboard'
  | 'athlete'
  | 'report'
  | 'brand_match'
  | 'query_results'
  | 'alerts'
  | 'watchlist'

export function useTerminalState() {
  const [activeView, setActiveView] = useState<View>('leaderboard')
  const [selectedAthlete, setSelectedAthlete] = useState<string | null>(null)
  const [queryResult, setQueryResult] = useState<Record<string, unknown> | null>(null)
  const [isQuerying, setIsQuerying] = useState(false)

  const { data: watchlistData } = useQuery({
    queryKey: ['watchlist'],
    queryFn: () => axios.get(`${API}/v1/watchlist`).then((r) => r.data),
    staleTime: 1000 * 60 * 5,
  })

  const { data: alertsData } = useQuery({
    queryKey: ['alerts'],
    queryFn: () => axios.get(`${API}/v1/alerts`).then((r) => r.data),
    staleTime: 1000 * 60,
    refetchInterval: 1000 * 60,
  })

  useEffect(() => {
    if (selectedAthlete) {
      setActiveView('athlete')
    }
  }, [selectedAthlete])

  const submitQuery = useCallback(
    async (queryText: string) => {
      if (!queryText.trim()) return
      setIsQuerying(true)
      setQueryResult({ status: 'thinking', query: queryText })

      try {
        const response = await axios.post(`${API}/v1/query`, {
          query: queryText,
          user_id: 'demo',
          context: {
            current_view: activeView,
            selected_athlete: selectedAthlete,
          },
        })

        const result = response.data as {
          athlete_ids?: string[]
          query_type?: string
        }

        if (result.athlete_ids?.length === 1) {
          setSelectedAthlete(result.athlete_ids[0])
          setActiveView('athlete')
        } else if (result.athlete_ids && result.athlete_ids.length > 1) {
          setActiveView('query_results')
        } else if (result.query_type === 'brand_match') {
          setActiveView('brand_match')
        } else if (result.query_type === 'deal_assessment') {
          setActiveView('report')
        }

        setQueryResult({ status: 'complete', ...result })
      } catch {
        setQueryResult({
          status: 'error',
          response: 'Query failed. Check API at VITE_API_URL and CORS.',
        })
      } finally {
        setIsQuerying(false)
      }
    },
    [activeView, selectedAthlete],
  )

  return {
    activeView,
    setActiveView,
    selectedAthlete,
    setSelectedAthlete,
    queryResult,
    setQueryResult,
    isQuerying,
    submitQuery,
    watchlist: watchlistData || { athletes: [] },
    alerts: alertsData || { unread: 0, items: [] },
  }
}
