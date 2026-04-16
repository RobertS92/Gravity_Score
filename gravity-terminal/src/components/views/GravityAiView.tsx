import { useEffect, useRef, useState } from 'react'
import { useAthleteStore } from '../../stores/athleteStore'
import { useGravityAiStore } from '../../stores/gravityAiStore'
import styles from './GravityAiView.module.css'

const SUGGESTED_PROMPTS = [
  'Which athletes on my watchlist have the strongest NIL velocity right now?',
  'Find me a Big 12 receiver under $300K with low risk',
  'Explain the top CFB quarterback\'s Brand score',
  'Compare the top 5 CFB quarterbacks by NIL range',
]

/** Inline data table for structured agent responses */
function InlineTable({ rows }: { rows: Record<string, unknown>[] }) {
  if (!rows.length) return null
  const keys = Object.keys(rows[0])
  return (
    <div className={styles.tableWrap}>
      <table className={styles.table}>
        <thead>
          <tr>{keys.map((k) => <th key={k}>{k.toUpperCase().replace(/_/g, ' ')}</th>)}</tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {keys.map((k) => (
                <td key={k}>{String(row[k] ?? '—')}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

/** Parse agent text for JSON arrays to render as inline tables */
function MessageContent({ content }: { content: string }) {
  const jsonMatch = content.match(/```(?:json)?\s*(\[[\s\S]*?\])\s*```/)
  if (jsonMatch) {
    try {
      const rows = JSON.parse(jsonMatch[1]) as Record<string, unknown>[]
      const before = content.slice(0, content.indexOf('```')).trim()
      const after = content.slice(content.indexOf('```') + jsonMatch[0].length).trim()
      return (
        <div>
          {before && <p className={styles.msgText}>{before}</p>}
          <InlineTable rows={rows} />
          {after && <p className={styles.msgText}>{after}</p>}
        </div>
      )
    } catch {
      /* fall through to plain text */
    }
  }
  return <p className={styles.msgText}>{content}</p>
}

export function GravityAiView() {
  const {
    conversations,
    activeConversationId,
    isStreaming,
    streamingText,
    contextAthleteId,
    contextAthleteName,
    contextAthleteGS,
    newConversation,
    loadConversations,
    selectConversation,
    sendMessage,
    stopStreaming,
    clearContext,
    setContext,
  } = useGravityAiStore()

  const activeAthlete = useAthleteStore((s) => s.activeAthlete)
  const [input, setInput] = useState('')
  const [streamAccum, setStreamAccum] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Inject active athlete as context when entering the view
  useEffect(() => {
    loadConversations()
    if (activeAthlete) {
      setContext(activeAthlete.athlete_id, activeAthlete.name, activeAthlete.gravity_score ?? null)
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const activeConv = conversations.find((c) => c.id === activeConversationId) ?? null
  const messages = activeConv?.messages ?? []

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, streamingText])

  const handleSend = async () => {
    const text = input.trim()
    if (!text || isStreaming) return
    setInput('')
    setStreamAccum('')
    if (!activeConversationId) newConversation()
    await sendMessage(text, (delta) => {
      setStreamAccum((prev) => prev + delta)
    })
    setStreamAccum('')
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      void handleSend()
    }
  }

  const handleSuggestion = (prompt: string) => {
    setInput(prompt)
    textareaRef.current?.focus()
  }

  const recentConvs = conversations.slice(0, 10)

  return (
    <div className={styles.root}>
      {/* ── Conversation history sidebar ── */}
      <aside className={styles.historyPanel}>
        <div className={styles.historyHeader}>CONVERSATIONS</div>
        <button className={styles.newConvBtn} onClick={() => { newConversation(); setStreamAccum('') }}>
          + NEW
        </button>
        <div className={styles.historyList}>
          {recentConvs.map((c) => (
            <button
              key={c.id}
              className={`${styles.historyItem} ${c.id === activeConversationId ? styles.historyItemActive : ''}`}
              onClick={() => selectConversation(c.id)}
            >
              <span className={styles.historyTitle}>{c.title}</span>
              <span className={styles.historyDate}>
                {new Date(c.updatedAt).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              </span>
            </button>
          ))}
          {!recentConvs.length && (
            <p className={styles.historyEmpty}>No conversations yet.</p>
          )}
        </div>
      </aside>

      {/* ── Main chat panel ── */}
      <div className={styles.chatPanel}>
        {/* Context banner */}
        {contextAthleteName && (
          <div className={styles.contextBanner}>
            <span className={styles.contextLabel}>CONTEXT:</span>
            <span className={styles.contextValue}>
              {contextAthleteName}
              {contextAthleteGS != null ? ` · GS ${contextAthleteGS.toFixed(1)}` : ''}
              {contextAthleteId ? ` · ${contextAthleteId.slice(0, 8)}` : ''}
            </span>
            <button className={styles.clearCtx} onClick={clearContext}>✕ CLEAR</button>
          </div>
        )}

        {/* Messages */}
        <div className={styles.messages}>
          {!messages.length && !isStreaming && (
            <div className={styles.emptyState}>
              <p className={styles.emptyTitle}>GRAVITY AI</p>
              <p className={styles.emptySub}>
                Ask anything about Power 5 CFB and NCAAB athlete data, NIL valuations, comparables, and market signals.
              </p>
              <div className={styles.suggestions}>
                {SUGGESTED_PROMPTS.map((p) => (
                  <button key={p} className={styles.suggestionBtn} onClick={() => handleSuggestion(p)}>
                    {p}
                  </button>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`${styles.msg} ${msg.role === 'user' ? styles.msgUser : styles.msgAssistant}`}
            >
              {msg.role === 'assistant' && (
                <span className={styles.msgLabel}>GRAVITY AI</span>
              )}
              <MessageContent content={msg.content} />
              <span className={styles.msgTime}>
                {new Date(msg.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' })}
              </span>
            </div>
          ))}

          {/* Streaming in-progress */}
          {isStreaming && streamAccum && (
            <div className={`${styles.msg} ${styles.msgAssistant}`}>
              <span className={styles.msgLabel}>GRAVITY AI</span>
              <p className={styles.msgText}>
                {streamAccum}
                <span className={styles.cursor}>▊</span>
              </p>
            </div>
          )}
          {isStreaming && !streamAccum && (
            <div className={`${styles.msg} ${styles.msgAssistant}`}>
              <span className={styles.msgLabel}>GRAVITY AI</span>
              <p className={styles.msgText}>
                <span className={styles.cursor}>▊</span>
              </p>
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className={styles.inputRow}>
          <textarea
            ref={textareaRef}
            className={styles.textarea}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask Gravity AI… (Enter to send, Shift+Enter for newline)"
            rows={2}
            disabled={isStreaming}
          />
          {isStreaming ? (
            <button className={`${styles.sendBtn} ${styles.stopBtn}`} onClick={stopStreaming}>
              ■ STOP
            </button>
          ) : (
            <button
              className={styles.sendBtn}
              onClick={() => void handleSend()}
              disabled={!input.trim()}
            >
              SEND
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
