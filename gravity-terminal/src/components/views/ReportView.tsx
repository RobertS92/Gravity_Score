export function ReportView({
  result,
}: {
  result: Record<string, unknown> | null
}) {
  const text = (result?.response as string) || JSON.stringify(result, null, 2)
  return (
    <div className="flex-1 overflow-auto p-6">
      <h3 className="text-sm text-[#6EA8FE] mb-3">Deal / report</h3>
      <pre className="text-xs text-[#94A3B8] whitespace-pre-wrap bg-[#121821] border border-[#202938] p-4 rounded">
        {text}
      </pre>
    </div>
  )
}
