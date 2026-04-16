import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { tryApplyAgentResponseText } from '../../agent/applyAgentResult'
import { runAgentCommand } from '../../agent/claudeClient'
import { parseStructuredCommand, resolveAthleteByName } from '../../agent/commandParser'
import { useAthleteStore } from '../../stores/athleteStore'
import { useCommandStore } from '../../stores/commandStore'
import { useUiStore } from '../../stores/uiStore'
import { useWatchlistStore } from '../../stores/watchlistStore'
import styles from './CommandBar.module.css'

const PLACEHOLDERS = [
  'score --athlete "Arch Manning"',
  'deal --assess $175K apparel',
  'csc --report',
  'brand --match $400K Southeast',
]

const KEYWORDS = [
  'score --athlete ""',
  'watchlist --add ""',
  'watchlist --remove ""',
  'csc --report',
  'brand --match ',
  'compare "" ""',
  'scan --position WR --conference Big12',
]

export function CommandBar() {
  const navigate = useNavigate()
  const inputRef = useRef<HTMLInputElement>(null)
  const [phIdx, setPhIdx] = useState(0)
  const [suggestOpen, setSuggestOpen] = useState(false)
  const [suggestions, setSuggestions] = useState<string[]>([])
  const [focusIdx, setFocusIdx] = useState(0)

  const value = useUiStore((s) => s.commandBarValue)
  const setValue = useUiStore((s) => s.setCommandBarValue)
  const pushHistory = useUiStore((s) => s.pushHistory)
  const historyPrev = useUiStore((s) => s.historyPrev)
  const historyNext = useUiStore((s) => s.historyNext)

  const setActive = useAthleteStore((s) => s.setActiveAthlete)
  const addWl = useWatchlistStore((s) => s.addToWatchlist)
  const removeWl = useWatchlistStore((s) => s.removeFromWatchlist)
  const wl = useWatchlistStore((s) => s.athletes)
  const setBrandSummary = useUiStore((s) => s.setBrandMatchSummary)
  const setCohort = useUiStore((s) => s.setCohortIds)
  const setMarketScanSub = useUiStore((s) => s.setMarketScanSub)

  const isProcessing = useCommandStore((s) => s.isProcessing)
  const setProcessing = useCommandStore((s) => s.setProcessing)
  const error = useCommandStore((s) => s.error)
  const setLast = useCommandStore((s) => s.setLast)
  const clearErr = useCommandStore((s) => s.clearError)

  useEffect(() => {
    const t = setInterval(() => setPhIdx((i) => (i + 1) % PLACEHOLDERS.length), 4000)
    return () => clearInterval(t)
  }, [])

  const placeholder = value ? '' : PLACEHOLDERS[phIdx]

  const buildSuggestions = useCallback(
    (prefix: string) => {
      const p = prefix.trim().toLowerCase()
      const names = wl.map((a) => a.name)
      const fromNames = names.filter((n) => n.toLowerCase().includes(p))
      const fromKw = KEYWORDS.filter((k) => k.toLowerCase().includes(p))
      return [...new Set([...fromNames.slice(0, 6), ...fromKw.slice(0, 6)])]
    },
    [wl],
  )

  const runLine = async (line: string) => {
    const trimmed = line.trim()
    if (!trimmed) return
    clearErr()
    pushHistory(trimmed)

    const parsed = parseStructuredCommand(trimmed)
    if (parsed.kind === 'scope_reject') {
      setLast(
        trimmed,
        `OUT OF SCOPE — GRAVITY COVERS POWER 5 CFB, NCAAB, AND NCAAWB ONLY.`,
        null,
      )
      return
    }

    if (parsed.kind === 'score') {
      const id = await resolveAthleteByName(parsed.name)
      if (!id) {
        setLast(trimmed, null, 'Athlete not found.')
        return
      }
      await setActive(id)
      navigate('/')
      setLast(trimmed, `Loaded athlete.`, null)
      return
    }

    if (parsed.kind === 'watchlist_add') {
      const id = await resolveAthleteByName(parsed.name)
      if (!id) {
        setLast(trimmed, null, 'Athlete not found.')
        return
      }
      await addWl(id)
      setLast(trimmed, 'Added to watchlist.', null)
      return
    }

    if (parsed.kind === 'watchlist_remove') {
      const id = await resolveAthleteByName(parsed.name)
      if (!id) {
        setLast(trimmed, null, 'Athlete not found.')
        return
      }
      await removeWl(id)
      setLast(trimmed, 'Removed from watchlist.', null)
      return
    }

    if (parsed.kind === 'csc_report') {
      navigate('/csc')
      setLast(trimmed, 'CSC Reports.', null)
      return
    }

    if (parsed.kind === 'brand_match') {
      setBrandSummary(parsed.rest)
      navigate('/brand-match')
      setLast(trimmed, 'Brand Match.', null)
      return
    }

    if (parsed.kind === 'compare') {
      const ids: string[] = []
      for (const n of parsed.names) {
        const id = await resolveAthleteByName(n)
        if (id) ids.push(id)
      }
      setCohort(ids.slice(0, 5))
      setMarketScanSub('cohort')
      navigate('/market-scan')
      setLast(trimmed, 'Cohort compare.', null)
      return
    }

    if (parsed.kind === 'scan') {
      setMarketScanSub('position')
      navigate('/market-scan')
      setLast(trimmed, `Market Scan${parsed.position ? ` · ${parsed.position}` : ''}${parsed.conference ? ` · ${parsed.conference}` : ''}.`, null)
      return
    }

    setProcessing(true)
    try {
      const out = await runAgentCommand(trimmed)
      await tryApplyAgentResponseText(out, navigate)
      setLast(trimmed, out, null)
    } catch (e) {
      setLast(trimmed, null, e instanceof Error ? e.message : 'Agent failed')
    } finally {
      setProcessing(false)
    }
  }

  const onSubmit = async () => {
    const line = value
    setValue('')
    await runLine(line)
    inputRef.current?.focus()
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      e.preventDefault()
      void onSubmit()
      return
    }
    if (e.key === 'ArrowUp') {
      e.preventDefault()
      historyPrev()
      return
    }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (suggestOpen && suggestions.length) {
        setFocusIdx((i) => (i + 1) % suggestions.length)
        return
      }
      historyNext()
      return
    }
    if (e.key === 'Tab') {
      e.preventDefault()
      const sug = buildSuggestions(value)
      setSuggestions(sug)
      setSuggestOpen(true)
      setFocusIdx(0)
      return
    }
    if (e.key === 'Escape') {
      setSuggestOpen(false)
    }
  }

  const promptCls = `${styles.prompt} ${isProcessing ? styles.promptBlink : ''} ${error ? styles.promptError : ''}`

  const applySuggestion = (s: string) => {
    setValue(s)
    setSuggestOpen(false)
    inputRef.current?.focus()
  }

  const hint = useMemo(() => '\u2191\u2193 history \u00b7 Tab complete', [])

  return (
    <div className={styles.bar}>
      <span className={promptCls}>gravity&gt;</span>
      {error && <span className={styles.errorInline}>{error}</span>}
      <div className={styles.suggestWrap}>
        <input
          ref={inputRef}
          className={styles.input}
          value={value}
          placeholder={placeholder}
          onChange={(e) => {
            clearErr()
            setValue(e.target.value)
          }}
          onKeyDown={onKeyDown}
          aria-label="Command input"
        />
        {suggestOpen && suggestions.length > 0 && (
          <div className={styles.suggestions} role="listbox">
            {suggestions.map((s, i) => (
              <button
                key={s}
                type="button"
                role="option"
                className={`${styles.suggestion} ${i === focusIdx ? styles.suggestionFocus : ''}`}
                onMouseDown={(ev) => ev.preventDefault()}
                onClick={() => applySuggestion(s)}
              >
                {s}
              </button>
            ))}
          </div>
        )}
      </div>
      <span className={styles.hint}>{hint}</span>
    </div>
  )
}
