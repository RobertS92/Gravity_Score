export function QueryResults({
  result,
  onSelectAthlete,
}: {
  result: Record<string, unknown> | null
  onSelectAthlete: (id: string) => void
}) {
  const ids = (result?.athlete_ids as string[] | undefined) || []

  if (ids.length === 0) {
    return (
      <div className="flex-1 p-6 text-sm text-[#94A3B8]">
        No athlete IDs in last query result.
        <pre className="mt-4 text-xs text-[#4A5568] whitespace-pre-wrap">
          {JSON.stringify(result, null, 2)}
        </pre>
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-auto p-6">
      <h3 className="text-sm text-[#6EA8FE] mb-3">Results ({ids.length})</h3>
      <ul className="space-y-1">
        {ids.map((id) => (
          <li key={id}>
            <button
              type="button"
              onClick={() => onSelectAthlete(id)}
              className="text-xs text-[#6EA8FE] hover:underline"
            >
              {id}
            </button>
          </li>
        ))}
      </ul>
    </div>
  )
}
