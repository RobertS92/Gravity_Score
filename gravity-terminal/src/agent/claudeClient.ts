import Anthropic from '@anthropic-ai/sdk'
import { apiPost } from '../api/client'
import { runTool, TOOL_DEFINITIONS } from './tools'

const MODEL = 'claude-sonnet-4-5'

const GRAVITY_SYSTEM = `You are Gravity AI, a commercial intelligence assistant for the college NIL market.
You have access to real-time athlete data for Power 5 CFB and NCAAB mens athletes including Gravity Scores, component scores, NIL valuations, comparables, and market signals.
Answer every question using the data tools available to you — do not speculate or use general knowledge when the answer is in the database.
Be direct and precise. Users are attorneys, agents, and brand managers making financially significant decisions.
Format numerical data clearly. When you do not have enough data to answer confidently, say so explicitly and tell the user what data would be needed.
Never provide legal advice. If asked about contracts or legal matters, provide commercial data context and state: THIS IS COMMERCIAL INTELLIGENCE DATA, NOT LEGAL ADVICE.
Scope: Power 5 CFB and NCAAB mens only. For any other league or sport, respond: THIS ATHLETE IS OUTSIDE GRAVITY'S CURRENT COVERAGE — POWER 5 CFB AND NCAAB MENS ONLY.`

export type ConversationMessage = { role: 'user' | 'assistant'; content: string }

/** Non-streaming command bar agent — returns full string */
export async function runAgentCommand(userText: string): Promise<string> {
  if (import.meta.env.VITE_AGENT_USE_PROXY === 'true') {
    try {
      const r = await apiPost<{ text: string }>('agent/complete', {
        prompt: userText,
        context: {},
      })
      return (r.text ?? '').trim() || '(no response)'
    } catch (e) {
      return `Agent proxy error: ${e instanceof Error ? e.message : String(e)}`
    }
  }

  const key = import.meta.env.VITE_ANTHROPIC_API_KEY as string | undefined
  if (!key?.trim()) {
    return (
      'Agent unavailable: set VITE_AGENT_USE_PROXY=true with a live API (server holds ANTHROPIC_API_KEY), ' +
      'or set VITE_ANTHROPIC_API_KEY for local browser-only demos.'
    )
  }

  const client = new Anthropic({ apiKey: key, dangerouslyAllowBrowser: true })

  const tools = TOOL_DEFINITIONS.map((t) => ({
    name: t.name,
    description: t.description,
    input_schema: t.input_schema as unknown as Anthropic.Tool.InputSchema,
  }))

  const messages: Anthropic.MessageParam[] = [{ role: 'user', content: userText }]

  let steps = 0
  while (steps < 6) {
    steps += 1
    const msg = await client.messages.create({
      model: MODEL,
      max_tokens: 1024,
      tools,
      messages,
    })

    const textParts: string[] = []
    const toolUses: { id: string; name: string; input: unknown }[] = []

    for (const b of msg.content) {
      if (b.type === 'text') textParts.push(b.text)
      if (b.type === 'tool_use') toolUses.push({ id: b.id, name: b.name, input: b.input })
    }

    if (msg.stop_reason === 'end_turn' && !toolUses.length) {
      return textParts.join('\n').trim() || '(no response)'
    }

    messages.push({ role: 'assistant', content: msg.content })

    if (toolUses.length) {
      const results: Anthropic.ToolResultBlockParam[] = []
      for (const tu of toolUses) {
        const input = (tu.input ?? {}) as Record<string, unknown>
        const out = await runTool(tu.name, input)
        results.push({ type: 'tool_result', tool_use_id: tu.id, content: out })
      }
      messages.push({ role: 'user', content: results })
    }
  }

  return 'Agent stopped: max tool steps.'
}

/**
 * Streaming agent for Gravity AI chat.
 * Calls the onDelta callback with each token as it arrives.
 * Returns the full accumulated text when done.
 */
export async function runAgentCommandStream(
  userText: string,
  history: ConversationMessage[],
  onDelta: (delta: string) => void,
  signal?: AbortSignal,
): Promise<string> {
  const key = import.meta.env.VITE_ANTHROPIC_API_KEY as string | undefined
  if (!key?.trim()) {
    const msg = 'Gravity AI requires VITE_ANTHROPIC_API_KEY or VITE_AGENT_USE_PROXY=true.'
    onDelta(msg)
    return msg
  }

  if (signal?.aborted) return '(stopped)'

  const client = new Anthropic({ apiKey: key, dangerouslyAllowBrowser: true })

  const tools = TOOL_DEFINITIONS.map((t) => ({
    name: t.name,
    description: t.description,
    input_schema: t.input_schema as unknown as Anthropic.Tool.InputSchema,
  }))

  // Build message history from conversation (last 20 turns)
  const messages: Anthropic.MessageParam[] = [
    ...history.slice(-18).map((m) => ({ role: m.role as 'user' | 'assistant', content: m.content })),
    { role: 'user', content: userText },
  ]

  let fullText = ''
  let steps = 0

  while (steps < 6) {
    steps += 1
    if (signal?.aborted) break

    // Use streaming for the final text generation, non-streaming for tool calls
    const hasToolInHistory = messages.some(
      (m) => typeof m.content !== 'string' && Array.isArray(m.content),
    )

    if (!hasToolInHistory && steps === 1) {
      // Stream the first response
      const stream = await client.messages.stream({
        model: MODEL,
        max_tokens: 2048,
        system: GRAVITY_SYSTEM,
        tools,
        messages,
      })

      const toolUses: { id: string; name: string; input: unknown }[] = []
      let pendingToolInput = ''
      let pendingToolId = ''
      let pendingToolName = ''

      for await (const event of stream) {
        if (signal?.aborted) break
        if (event.type === 'content_block_delta') {
          const delta = event.delta
          if (delta.type === 'text_delta') {
            fullText += delta.text
            onDelta(delta.text)
          } else if (delta.type === 'input_json_delta') {
            pendingToolInput += delta.partial_json
          }
        } else if (event.type === 'content_block_start') {
          if (event.content_block.type === 'tool_use') {
            pendingToolId = event.content_block.id
            pendingToolName = event.content_block.name
            pendingToolInput = ''
          }
        } else if (event.type === 'content_block_stop' && pendingToolId) {
          try {
            toolUses.push({ id: pendingToolId, name: pendingToolName, input: JSON.parse(pendingToolInput || '{}') })
          } catch {
            toolUses.push({ id: pendingToolId, name: pendingToolName, input: {} })
          }
          pendingToolId = ''
          pendingToolName = ''
          pendingToolInput = ''
        }
      }

      const finalMsg = await stream.finalMessage()

      if (!toolUses.length) {
        return fullText || finalMsg.content.map((b) => (b.type === 'text' ? b.text : '')).join('')
      }

      // Has tool calls — execute them and continue
      messages.push({ role: 'assistant', content: finalMsg.content })
      const results: Anthropic.ToolResultBlockParam[] = []
      for (const tu of toolUses) {
        const out = await runTool(tu.name, (tu.input ?? {}) as Record<string, unknown>)
        results.push({ type: 'tool_result', tool_use_id: tu.id, content: out })
      }
      messages.push({ role: 'user', content: results })
    } else {
      // Non-streaming for follow-up after tool calls
      const msg = await client.messages.create({
        model: MODEL,
        max_tokens: 2048,
        system: GRAVITY_SYSTEM,
        tools,
        messages,
      })

      const textParts: string[] = []
      const toolUses: { id: string; name: string; input: unknown }[] = []

      for (const b of msg.content) {
        if (b.type === 'text') textParts.push(b.text)
        if (b.type === 'tool_use') toolUses.push({ id: b.id, name: b.name, input: b.input })
      }

      if (!toolUses.length) {
        const text = textParts.join('\n').trim()
        // Stream the text token-by-token simulation for tool-result responses
        const words = text.split(' ')
        for (const word of words) {
          if (signal?.aborted) break
          onDelta(word + ' ')
          fullText += word + ' '
          await new Promise((r) => setTimeout(r, 8))
        }
        return fullText.trim()
      }

      messages.push({ role: 'assistant', content: msg.content })
      const results: Anthropic.ToolResultBlockParam[] = []
      for (const tu of toolUses) {
        const out = await runTool(tu.name, (tu.input ?? {}) as Record<string, unknown>)
        results.push({ type: 'tool_result', tool_use_id: tu.id, content: out })
      }
      messages.push({ role: 'user', content: results })
    }
  }

  return fullText || 'Agent stopped: max steps.'
}
