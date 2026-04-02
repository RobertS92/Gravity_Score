export function AthleteProfile({
  data,
}: {
  data: unknown
  onSelectAthlete: (id: string) => void
}) {
  if (!data) {
    return (
      <div className="flex-1 flex items-center justify-center text-[#4A5568] text-sm">
        Select an athlete
      </div>
    )
  }

  const d = data as {
    athlete?: Record<string, unknown>
    score_history?: unknown[]
  }
  const a = d.athlete || {}

  return (
    <div className="flex-1 overflow-auto p-6 max-w-3xl">
      <h2 className="text-lg text-[#6EA8FE] mb-1">{String(a.name || '')}</h2>
      <p className="text-xs text-[#94A3B8] mb-4">
        {String(a.school || '')} · {String(a.conference || '')} · {String(a.sport || '')}
      </p>
      <pre className="text-[10px] bg-[#121821] border border-[#202938] p-3 rounded overflow-x-auto text-[#94A3B8]">
        {JSON.stringify(
          { athlete: a, history_len: d.score_history?.length ?? 0 },
          null,
          2,
        )}
      </pre>
    </div>
  )
}
