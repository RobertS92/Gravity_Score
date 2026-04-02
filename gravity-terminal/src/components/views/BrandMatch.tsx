export function BrandMatch({
  result,
  onSelectAthlete,
}: {
  result: Record<string, unknown> | null
  onSelectAthlete: (id: string) => void
}) {
  const ids = (result?.athlete_ids as string[] | undefined) || []
  return (
    <div className="flex-1 overflow-auto p-6">
      <h3 className="text-sm text-[#6EA8FE] mb-3">Brand match</h3>
      <p className="text-xs text-[#94A3B8] mb-4 whitespace-pre-wrap">
        {(result?.response as string) || ''}
      </p>
      {ids.length > 0 && (
        <ul className="space-y-1">
          {ids.map((id) => (
            <li key={id}>
              <button
                type="button"
                className="text-xs text-[#6EA8FE] hover:underline"
                onClick={() => onSelectAthlete(id)}
              >
                {id}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
