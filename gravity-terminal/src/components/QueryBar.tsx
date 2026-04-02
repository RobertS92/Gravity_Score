import { useRef, useState, type KeyboardEvent } from 'react'

const QUERY_SUGGESTIONS = [
  'SEC wide receivers with Brand score above 65',
  'Assess a $200K endorsement deal for Travis Hunter',
  'Top 10 rising athletes by velocity score',
  'Find athletes for a regional bank campaign, max risk 25',
  'Power 5 point guards with high brand, low risk',
]

interface QueryBarProps {
  onSubmit: (query: string) => void
  isQuerying: boolean
}

export function QueryBar({ onSubmit, isQuerying }: QueryBarProps) {
  const [value, setValue] = useState('')
  const [showSuggestions, setShowSuggestions] = useState(false)
  const inputRef = useRef<HTMLInputElement>(null)

  const handleSubmit = () => {
    if (!value.trim() || isQuerying) return
    onSubmit(value.trim())
    setValue('')
    setShowSuggestions(false)
  }

  const handleKeyDown = (e: KeyboardEvent) => {
    if (e.key === 'Enter') handleSubmit()
    if (e.key === 'Escape') setShowSuggestions(false)
  }

  return (
    <div className="border-t border-[#202938] bg-[#0B0F14] p-3 shrink-0">
      {showSuggestions && !isQuerying && (
        <div className="mb-2 flex flex-wrap gap-2">
          {QUERY_SUGGESTIONS.map((s, i) => (
            <button
              key={i}
              type="button"
              onClick={() => {
                setValue(s)
                inputRef.current?.focus()
              }}
              className="text-xs bg-[#1A2433] text-[#6EA8FE] border border-[#202938] px-2 py-1 rounded hover:border-[#6EA8FE] transition-colors"
            >
              {s}
            </button>
          ))}
        </div>
      )}

      <div className="flex items-center gap-3 bg-[#121821] border border-[#202938] rounded px-3 py-2 focus-within:border-[#6EA8FE] transition-colors">
        <span className="text-[#6EA8FE] text-sm font-bold shrink-0">
          {isQuerying ? '⟳' : '›'}
        </span>
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          onFocus={() => setShowSuggestions(true)}
          placeholder={
            isQuerying
              ? 'Agent running...'
              : 'Query athletes, assess deals, find brand matches...'
          }
          disabled={isQuerying}
          className="flex-1 bg-transparent text-sm text-[#E6EDF3] placeholder-[#4A5568] outline-none disabled:opacity-50"
        />
        {value && (
          <button
            type="button"
            onClick={handleSubmit}
            disabled={isQuerying}
            className="shrink-0 text-xs bg-[#6EA8FE] text-[#0B0F14] px-3 py-1 rounded font-bold hover:bg-[#5B97F0] disabled:opacity-50 transition-colors"
          >
            RUN
          </button>
        )}
      </div>

      <div className="flex items-center justify-between mt-1.5 px-1">
        <span className="text-xs text-[#4A5568]">
          Enter to run · Esc to close suggestions
        </span>
        <span className="text-xs text-[#4A5568]">Gravity NIL Intelligence v1.0</span>
      </div>
    </div>
  )
}
