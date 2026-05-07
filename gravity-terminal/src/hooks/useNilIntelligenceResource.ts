import { useEffect, useState } from 'react'

type Fetcher<T> = (athleteId: string) => Promise<T>

export function useNilIntelligenceResource<T>(
  athleteId: string,
  fetcher: Fetcher<T>,
  fallbackError: string,
) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let active = true
    setLoading(true)
    setError(null)
    void fetcher(athleteId)
      .then((res) => {
        if (!active) return
        setData(res)
      })
      .catch((e: unknown) => {
        if (!active) return
        setError(e instanceof Error ? e.message : fallbackError)
      })
      .finally(() => {
        if (!active) return
        setLoading(false)
      })
    return () => {
      active = false
    }
  }, [athleteId, fetcher, fallbackError])

  return { data, loading, error }
}
