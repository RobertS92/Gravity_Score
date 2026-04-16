import { create } from 'zustand'
import { apiGet, apiPost } from '../api/client'
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

interface GravityAiStore {
  conversations: Conversation[]
  activeConversationId: string | null
  isStreaming: boolean
  streamingText: string
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
    set((s) => ({ conversations: [conv, ...s.conversations], activeConversationId: id }))
    _saveConversations(get().conversations)
    return id
  },

  loadConversations: async () => {
    // Load from localStorage first (immediate), then sync with Supabase if available
    const local = _loadLocalConversations()
    if (local.length) set({ conversations: local })

    try {
      const userId = getTerminalUserId()
      const remote = await apiGet<Conversation[]>(`agent/conversations?user_id=${userId}`)
      if (remote?.length) {
        set({ conversations: remote })
        _saveConversations(remote)
      }
    } catch {
      // Offline / no backend endpoint — local storage is source of truth
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
      conversations: s.conversations.map((c) =>
        c.id === convId ? { ...c, messages: [...c.messages, userMsg], updatedAt: Date.now() } : c,
      ),
      isStreaming: true,
      streamingText: '',
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
        const res = await fetch(
          `${_apiBase()}/v1/agent/stream`,
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              Authorization: `Bearer ${_getToken()}`,
            },
            body: JSON.stringify({
              prompt: contextNote + text,
              history,
              context: { athleteId: contextAthleteId },
            }),
            signal: abortController.signal,
          },
        )

        if (res.ok && res.body) {
          const reader = res.body.getReader()
          const decoder = new TextDecoder()
          while (true) {
            const { done, value } = await reader.read()
            if (done) break
            const chunk = decoder.decode(value, { stream: true })
            // SSE lines: "data: {text}\n\n"
            for (const line of chunk.split('\n')) {
              if (line.startsWith('data: ')) {
                const delta = line.slice(6)
                if (delta === '[DONE]') break
                fullText += delta
                streamCallback(delta)
                set({ streamingText: fullText })
              }
            }
          }
        } else {
          // Proxy didn't support streaming — get full response
          const data = await res.json() as { text?: string }
          fullText = data.text ?? '(no response)'
          streamCallback(fullText)
        }
      } else {
        // Direct Anthropic SDK with streaming
        const { runAgentCommandStream } = await import('../agent/claudeClient')
        fullText = await runAgentCommandStream(contextNote + text, history, streamCallback, abortController.signal)
      }
    } catch (err: unknown) {
      if ((err as { name?: string }).name === 'AbortError') {
        fullText = fullText || '(stopped)'
      } else {
        fullText = `Error: ${err instanceof Error ? err.message : 'Agent failed'}`
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
      const conv = get().conversations.find((c) => c.id === convId)
      if (conv) {
        await apiPost('agent/conversations', { user_id: userId, conversation: conv })
      }
    } catch {
      // Best-effort only
    }
  },

  stopStreaming: () => {
    abortController?.abort()
    abortController = null
    set({ isStreaming: false, streamingText: '' })
  },
}))

// ── local storage helpers ─────────────────────────────────────────────────────
const LS_KEY = 'gravity_ai_conversations'

function _loadLocalConversations(): Conversation[] {
  try {
    const raw = localStorage.getItem(LS_KEY)
    if (!raw) return []
    return (JSON.parse(raw) as Conversation[]).slice(0, 20)
  } catch {
    return []
  }
}

function _saveConversations(convs: Conversation[]) {
  try {
    localStorage.setItem(LS_KEY, JSON.stringify(convs.slice(0, 20)))
  } catch {
    /* quota */
  }
}

function _apiBase() {
  const raw = (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, '') ?? ''
  return raw
}

function _getToken() {
  try { return localStorage.getItem('gravity_access_token') ?? '' } catch { return '' }
}
