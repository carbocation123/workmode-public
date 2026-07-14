import type { ChatStreamEvent, Message } from '../api'

export type LiteratureToolStatus = 'running' | 'completed' | 'failed' | 'cancelled'

export interface LiteratureChatMessage {
  id: string
  role: 'assistant' | 'user' | 'system' | 'tool'
  text: string
  paperIds?: string[]
  noteIds?: string[]
  sources?: string[]
  noteSources?: string[]
  toolCallId?: string
  toolName?: string
  toolArgs?: Record<string, unknown>
  toolStatus?: LiteratureToolStatus
  interrupted?: boolean
}

export interface LiveChatState {
  messages: LiteratureChatMessage[]
  runId: string
  nextSegment: number
  activeAssistantId: string | null
  contextPercent: number
  finished: boolean
}

function contextPercent(event: ChatStreamEvent, fallback: number): number {
  const context = event.context
  if (!context) return fallback
  const total = Number(
    context.total_tokens_estimate
    || context.estimated_prompt_tokens
    || context.prompt_tokens_estimate
    || 0,
  )
  const budget = Number(context.budget_tokens || 0)
  if (!budget) return 0
  return Math.min(100, Math.max(0, Math.round((total / budget) * 100)))
}

function metaString(message: Message | undefined, key: string): string {
  const value = message?.meta?.[key]
  return typeof value === 'string' ? value : ''
}

function eventMessage(event: ChatStreamEvent): Message | undefined {
  return event.message && typeof event.message === 'object' ? event.message : undefined
}

function metaObject(message: Message | undefined, key: string): Record<string, unknown> {
  const value = message?.meta?.[key]
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function toolStatus(event: ChatStreamEvent, message?: Message): LiteratureToolStatus {
  const status = metaString(message, 'status')
  if (status === 'running') return 'running'
  if (status === 'cancelled') return 'cancelled'
  if (status === 'done') return 'completed'
  if (status === 'error') return 'failed'
  if (event.type === 'tool_call_start') return 'running'
  return event.ok === false ? 'failed' : 'completed'
}

function toolMessage(event: ChatStreamEvent): LiteratureChatMessage {
  const message = eventMessage(event)
  const callId = metaString(message, 'tool_call_id') || String(event.id || message?.id || '')
  const name = metaString(message, 'tool_name') || String(event.name || 'tool')
  const args = Object.keys(metaObject(message, 'args')).length
    ? metaObject(message, 'args')
    : event.input || {}
  return {
    id: message?.id || `tool-${callId}`,
    role: 'tool',
    text: message?.content || String(event.result || ''),
    toolCallId: callId,
    toolName: name,
    toolArgs: args,
    toolStatus: toolStatus(event, message),
  }
}

export function createLiveChatState(
  messages: LiteratureChatMessage[],
  runId: string,
  currentContextPercent: number,
): LiveChatState {
  return {
    messages,
    runId,
    nextSegment: 0,
    activeAssistantId: null,
    contextPercent: currentContextPercent,
    finished: false,
  }
}

export function chatActionMessageForEvent(current: string, event: ChatStreamEvent): string {
  if (event.type === 'loop_continue') {
    return `工具调用完成，继续生成第 ${String(event.round || '?')} 轮…`
  }
  if (event.type === 'done' || event.type === 'error') return ''
  if (event.type === 'cancelled') return '本轮生成已停止。'
  return current
}

export function reduceLiveChatEvent(state: LiveChatState, event: ChatStreamEvent): LiveChatState {
  if (event.type === 'context_usage') {
    return { ...state, contextPercent: contextPercent(event, state.contextPercent) }
  }

  if (event.type === 'text_delta') {
    const content = String(event.content || '')
    if (!content) return state
    if (state.activeAssistantId) {
      return {
        ...state,
        messages: state.messages.map((message) => message.id === state.activeAssistantId
          ? { ...message, text: message.text + content }
          : message),
      }
    }
    const id = `stream-${state.runId}-${state.nextSegment}`
    return {
      ...state,
      nextSegment: state.nextSegment + 1,
      activeAssistantId: id,
      messages: [...state.messages, { id, role: 'assistant', text: content }],
    }
  }

  if (event.type === 'tool_call_start' || event.type === 'tool_result') {
    const incoming = toolMessage(event)
    const existingIndex = state.messages.findIndex((message) => (
      message.role === 'tool' && message.toolCallId === incoming.toolCallId
    ))
    const messages = [...state.messages]
    if (existingIndex >= 0) {
      const existing = messages[existingIndex]
      messages[existingIndex] = {
        ...existing,
        ...incoming,
        id: existing.id,
        toolArgs: Object.keys(incoming.toolArgs || {}).length ? incoming.toolArgs : existing.toolArgs,
      }
    } else {
      messages.push(incoming)
    }
    return { ...state, messages, activeAssistantId: null }
  }

  const persistedMessage = eventMessage(event)
  if (event.type === 'assistant_message' && persistedMessage?.role === 'assistant') {
    const persisted = persistedMessage
    if (state.activeAssistantId) {
      return {
        ...state,
        messages: state.messages.map((message) => message.id === state.activeAssistantId
          ? { ...message, text: persisted.content }
          : message),
      }
    }
    if (!persisted.content) return state
    return {
      ...state,
      messages: [...state.messages, {
        id: persisted.id,
        role: 'assistant',
        text: persisted.content,
        interrupted: persisted.meta?.interrupted === true,
      }],
    }
  }

  if (event.type === 'cancelled') {
    return {
      ...state,
      finished: true,
      messages: state.messages.map((message) => {
        if (message.id === state.activeAssistantId) return { ...message, interrupted: true }
        if (message.role === 'tool' && message.toolStatus === 'running') {
          return { ...message, toolStatus: 'cancelled' }
        }
        return message
      }),
    }
  }

  if (event.type === 'done') return { ...state, finished: true }
  return state
}
