import { create } from 'zustand'
import { apiGet, apiPost } from '../api/client'
import { getApiBaseUrlWithV1, getRawViteApiUrl } from '../lib/apiBaseUrl'
import { getTerminalUserId } from './authStore'

export type ChatRole = 'user' | 'assistant'

export interface ChatMessage {
  id: string
  role: ChatRole
  content: string
  /** Structured data rendered as inline table when present */
  tableData?: Record<string, unknown>[]
  timestamp: number
}

export interface Conversation {
  id: string
  title: string
  messages: ChatMessage[]
  contextAthleteId?: string
  contextAthleteName?: string
  createdAt: number
  updatedAt: number
}

const CONVERSATION_CAP = 20

interface GravityAiStore {
  conversations: Conversation[]
  activeConversationId: string | null
  isStreaming: boolean
  streamingText: string
  waitingMode: 'streaming' | 'processing' | null
  conversationSyncStatus: 'unknown' | 'synced' | 'local_only'
  contextAthleteId: string | null
  contextAthleteName: string | null
  contextAthleteGS: number | null

  // Actions
  setContext: (id: string | null, name: string | null, gs: number | null) => void
  clearContext: () => void
  newConversation: () => string
  loadConversations: () => Promise<void>
  selectConversation: (id: string) => void
  sendMessage: (text: string, streamCallback: (delta: string) => void) => Promise<void>
  stopStreaming: () => void
}

let abortController: AbortController | null = null

export const useGravityAiStore = create<GravityAiStore>((set, get) => ({
  conversations: [],
  activeConversationId: null,
  isStreaming: false,
  streamingText: '',
  waitingMode: null,
  conversationSyncStatus: 'unknown',
  contextAthleteId: null,
  contextAthleteName: null,
  contextAthleteGS: null,

  setContext: (id, name, gs) =>
    set({ contextAthleteId: id, contextAthleteName: name, contextAthleteGS: gs }),

  clearContext: () => set({ contextAthleteId: null, contextAthleteName: null, contextAthleteGS: null }),

  newConversation: () => {
    const id = crypto.randomUUID()
    const { contextAthleteId, contextAthleteName } = get()
    const conv: Conversation = {
      id,
      title: 'New conversation',
      messages: [],
      contextAthleteId: contextAthleteId ?? undefined,
      contextAthleteName: contextAthleteName ?? undefined,
      createdAt: Date.now(),
      updatedAt: Date.now(),
    }
    set((s) => ({ conversations: clampConversations([conv, ...s.conversations]), activeConversationId: id }))
    _saveConversations(get().conversations)
    return id
  },

  loadConversations: async () => {
    // Load from localStorage first (immediate), then sync with Supabase if available
    const local = _loadLocalConversations()
    if (local.length) set({ conversations: clampConversations(local) })

    try {
      const userId = getTerminalUserId()
      if (!userId) return
      const remote = await apiGet<Conversation[]>(`agent/conversations?user_id=${userId}`)
      if (remote?.length) {
        const trimmed = clampConversations(remote)
        set({ conversations: trimmed })
        _saveConversations(trimmed)
        set({ conversationSyncStatus: 'synced' })
      } else {
        set({ conversationSyncStatus: local.length > 0 ? 'local_only' : 'unknown' })
      }
    } catch {
      // Offline / no backend endpoint — local storage is source of truth
      set({ conversationSyncStatus: local.length > 0 ? 'local_only' : 'unknown' })
    }
  },

  selectConversation: (id) => set({ activeConversationId: id }),

  sendMessage: async (text, streamCallback) => {
    const state = get()
    let convId = state.activeConversationId
    if (!convId) {
      convId = get().newConversation()
    }

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: text,
      timestamp: Date.now(),
    }

    set((s) => ({
      conversations: clampConversations(s.conversations.map((c) =>
        c.id === convId ? { ...c, messages: [...c.messages, userMsg], updatedAt: Date.now() } : c,
      )),
      isStreaming: true,
      streamingText: '',
      waitingMode: 'streaming',
    }))

    abortController = new AbortController()
    let fullText = ''

    try {
      const conv = get().conversations.find((c) => c.id === convId)!
      const history = conv.messages.slice(-20).map((m) => ({ role: m.role, content: m.content }))

      const { contextAthleteId, contextAthleteName, contextAthleteGS } = get()
      const contextNote = contextAthleteName
        ? `Current context: ${contextAthleteName}${contextAthleteGS != null ? ` · GS ${contextAthleteGS.toFixed(1)}` : ''} (id: ${contextAthleteId}). `
        : ''

      // Try streaming endpoint first; fall back to non-streaming agent call
      const useProxy = import.meta.env.VITE_AGENT_USE_PROXY === 'true'

      if (useProxy) {
        fullText = await _runProxyAgent({
          prompt: contextNote + text,
          history,
          contextAthleteId,
          streamCallback,
          signal: abortController.signal,
          setWaiting: (mode) => set({ waitingMode: mode }),
          setStreamingText: (t) => set({ streamingText: t }),
        })
      } else {
        // Direct Anthropic SDK with streaming
        const { runAgentCommandStream } = await import('../agent/claudeClient')
        fullText = await runAgentCommandStream(contextNote + text, history, streamCallback, abortController.signal)
      }
    } catch (err: unknown) {
      if ((err as { name?: string }).name === 'AbortError') {
        fullText = fullText || '(stopped)'
      } else {
        fullText = `Error: ${_formatAgentError(err)}`
      }
    }

    const assistantMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: fullText,
      timestamp: Date.now(),
    }

    set((s) => ({
      isStreaming: false,
      streamingText: '',
      waitingMode: null,
      conversations: s.conversations.map((c) => {
        if (c.id !== convId) return c
        const updated = { ...c, messages: [...c.messages, assistantMsg], updatedAt: Date.now() }
        // Auto-title after first exchange
        if (c.messages.length === 1 && c.title === 'New conversation') {
          updated.title = text.slice(0, 40) + (text.length > 40 ? '…' : '')
        }
        return updated
      }),
    }))

    _saveConversations(get().conversations)

    // Persist to backend if available
    try {
      const userId = getTerminalUserId()
      if (!userId) return
      const conv = get().conversations.find((c) => c.id === convId)
      if (conv) {
        await apiPost('agent/conversations', { user_id: userId, conversation: conv })
        set({ conversationSyncStatus: 'synced' })
      }
    } catch {
      // Best-effort only
      set({ conversationSyncStatus: 'local_only' })
    }
  },

  stopStreaming: () => {
    abortController?.abort()
    abortController = null
    set({ isStreaming: false, streamingText: '', waitingMode: null })
  },
}))

// ── local storage helpers ─────────────────────────────────────────────────────
const LS_KEY = 'gravity_ai_conversations'

function _loadLocalConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (!raw) return []
    return clampConversations(JSON.parse(raw) as Conversation[])
  } catch {
    return []
  }
}

function _saveConversations(convs: Conversation[]) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(clampConversations(convs)))
  } catch {
    /* quota */
  }
}

function clampConversations(convs: Conversation[]): Conversation[] {
  return [...convs]
    .sort((a, b) => b.updatedAt - a.updatedAt)
    .slice(0, CONVERSATION_CAP)
}

/** Stream URL must use the same /v1-normalized base as apiPost — never raw+/v1. */
function _agentStreamUrl() {
  const base = getApiBaseUrlWithV1()
  if (!base) return '/v1/agent/stream'
  return `${base}/agent/stream`
}

function _getToken() {
  try { return localStorage.getItem('gravity_access_token') ?? '' } catch { return '' }
}

function _formatAgentError(err: unknown): string {
  const message = err instanceof Error ? err.message : 'Agent failed'
  if (/failed to fetch|network ?error|load failed|err_connection|cors/i.test(message)) {
    const base = getApiBaseUrlWithV1() || getRawViteApiUrl() || '(unset)'
    return (
      `Cannot reach Gravity AI at ${base}. Check VITE_API_URL / CORS / login, ` +
      `then retry. (${message})`
    )
  }
  return message
}

async function _completeFallback(
  prompt: string,
  history: { role: string; content: string }[],
  contextAthleteId: string | null,
): Promise<string> {
  try {
    const data = await apiPost<{ text?: string; detail?: unknown }>('agent/complete', {
      prompt,
      history,
      context: { athleteId: contextAthleteId },
    })
    if (typeof data?.text === 'string' && data.text.trim()) return data.text
    if (data?.detail != null) {
      return typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
    }
    return '(no response)'
  } catch (err: unknown) {
    throw err
  }
}

async function _runProxyAgent(args: {
  prompt: string
  history: { role: string; content: string }[]
  contextAthleteId: string | null
  streamCallback: (delta: string) => void
  signal: AbortSignal
  setWaiting: (mode: 'streaming' | 'processing' | null) => void
  setStreamingText: (t: string) => void
}): Promise<string> {
  const body = JSON.stringify({
    prompt: args.prompt,
    history: args.history,
    context: { athleteId: args.contextAthleteId },
  })

  let res: Response
  try {
    res = await fetch(_agentStreamUrl(), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${_getToken()}`,
      },
      body,
      signal: args.signal,
    })
  } catch (err) {
    // Stream connect failed — fall back to non-streaming complete.
    args.setWaiting('processing')
    const text = await _completeFallback(args.prompt, args.history, args.contextAthleteId)
    args.streamCallback(text)
    return text
  }

  if (res.ok && res.body) {
    let fullText = ''
    try {
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        const chunk = decoder.decode(value, { stream: true })
        for (const line of chunk.split('\n')) {
          if (line.startsWith('data: ')) {
            const delta = line.slice(6)
            if (delta === '[DONE]') break
            fullText += delta
            args.streamCallback(delta)
            args.setStreamingText(fullText)
          }
        }
      }
      if (fullText.trim()) return fullText
    } catch (err) {
      if ((err as { name?: string }).name === 'AbortError') throw err
      // Mid-stream abort — fall back to complete if we got nothing useful.
      if (!fullText.trim()) {
        args.setWaiting('processing')
        const text = await _completeFallback(args.prompt, args.history, args.contextAthleteId)
        args.streamCallback(text)
        return text
      }
      return fullText
    }
  }

  // Non-OK HTTP or empty stream body — prefer complete, else surface detail.
  args.setWaiting('processing')
  try {
    const text = await _completeFallback(args.prompt, args.history, args.contextAthleteId)
    args.streamCallback(text)
    return text
  } catch {
    try {
      const data = (await res.json()) as { text?: string; detail?: unknown }
      const detail =
        typeof data.detail === 'string'
          ? data.detail
          : data.detail != null
            ? JSON.stringify(data.detail)
            : null
      const fallback = data.text ?? detail ?? `(${res.status} ${res.statusText || 'no response'})`
      args.streamCallback(fallback)
      return fallback
    } catch {
      const fallback = `(${res.status} ${res.statusText || 'no response'})`
      args.streamCallback(fallback)
      return fallback
    }
  }
}
