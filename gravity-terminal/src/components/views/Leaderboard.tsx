import { useQuery } from '@tanstack/react-query'
import axios from 'axios'

const API = import.meta.env.VITE_API_URL || 'http://localhost:8000'

interface Row {
  id: string
  name: string
  school?: string
  conference?: string
  sport?: string
  gravity_score?: number | null
  brand_score?: number | null
}

export function Leaderboard({
  onSelectAthlete,
}: {
  onSelectAthlete: (id: string) => void
}) {
  const { data, isLoading, error } = useQuery({
    queryKey: ['leaderboard'],
    queryFn: () =>
      axios
        .get<{ athletes: Row[]; total?: number }>(`${API}/v1/athletes?limit=100`)
        .then((r) => r.data),
    staleTime: 60_000,
  })

  if (isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center text-[#6EA8FE]">
        Loading athletes…
      </div>
    )
  }

  if (error) {
    return (
      <div className="flex-1 p-6 text-sm text-[#D85A30]">
        Could not load <code>/v1/athletes</code>. Is the API running? ({String(error)})
      </div>
    )
  }

  const rows = data?.athletes ?? []

  return (
    <div className="flex-1 overflow-auto p-4">
      <h2 className="text-sm font-semibold text-[#94A3B8] mb-3">
        Leaderboard <span className="text-[#4A5568]">({data?.total ?? rows.length})</span>
      </h2>
      <div className="overflow-x-auto border border-[#202938] rounded">
        <table className="w-full text-left text-xs">
          <thead className="bg-[#121821] text-[#6EA8FE]">
            <tr>
              <th className="p-2">Name</th>
              <th className="p-2">School</th>
              <th className="p-2">Conf</th>
              <th className="p-2">Sport</th>
              <th className="p-2">Gravity</th>
              <th className="p-2">Brand</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((a) => (
              <tr
                key={a.id}
                className="border-t border-[#202938] hover:bg-[#121821] cursor-pointer"
                onClick={() => onSelectAthlete(a.id)}
              >
                <td className="p-2 text-[#E6EDF3]">{a.name}</td>
                <td className="p-2">{a.school}</td>
                <td className="p-2">{a.conference}</td>
                <td className="p-2">{a.sport}</td>
                <td className="p-2">
                  {a.gravity_score != null ? Number(a.gravity_score).toFixed(1) : '—'}
                </td>
                <td className="p-2">
                  {a.brand_score != null ? Number(a.brand_score).toFixed(1) : '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {rows.length === 0 && (
        <p className="mt-4 text-[#4A5568] text-xs">
          No rows yet — run roster ingestion and scoring (see migrations + weekly_refresh job).
        </p>
      )}
    </div>
  )
}
