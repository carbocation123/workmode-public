import type { Message } from './api'

export type ToolRunStatus = 'running' | 'done' | 'error'

export interface MessageConversationItem {
  kind: 'message'
  key: string
  message: Message
}

export interface ToolConversationItem {
  kind: 'tool'
  key: string
  callId: string
  toolName: string
  status: ToolRunStatus
  args: Record<string, unknown>
  result: string
  changedPaths: string[]
}

export type ConversationItem = MessageConversationItem | ToolConversationItem

function metaString(message: Message, key: string, fallback = '') {
  const value = message.meta[key]
  return typeof value === 'string' ? value : fallback
}

function metaObject(message: Message, key: string) {
  const value = message.meta[key]
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function metaStringArray(message: Message, key: string) {
  const value = message.meta[key]
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}

function normalizeStatus(value: string, fallback: ToolRunStatus): ToolRunStatus {
  return value === 'running' || value === 'done' || value === 'error' ? value : fallback
}

export function buildConversationItems(messages: Message[]): ConversationItem[] {
  const items: ConversationItem[] = []
  const toolIndexByCallId = new Map<string, number>()

  for (const message of messages) {
    if (message.role !== 'tool') {
      items.push({ kind: 'message', key: message.id, message })
      continue
    }

    const event = metaString(message, 'event')
    const callId = metaString(message, 'tool_call_id', message.id)
    const toolName = metaString(message, 'tool_name', 'tool')

    if (event === 'tool_call_start') {
      const item: ToolConversationItem = {
        kind: 'tool',
        key: `tool-${callId}`,
        callId,
        toolName,
        status: normalizeStatus(metaString(message, 'status'), 'running'),
        args: metaObject(message, 'args'),
        result: '',
        changedPaths: []
      }
      toolIndexByCallId.set(callId, items.length)
      items.push(item)
      continue
    }

    const existingIndex = toolIndexByCallId.get(callId)
    const existing = existingIndex === undefined ? null : items[existingIndex]
    const resultItem: ToolConversationItem = {
      kind: 'tool',
      key: `tool-${callId}`,
      callId,
      toolName,
      status: normalizeStatus(metaString(message, 'status'), 'done'),
      args: existing?.kind === 'tool' ? existing.args : {},
      result: message.content,
      changedPaths: metaStringArray(message, 'changed_paths')
    }
    if (existing?.kind === 'tool' && existingIndex !== undefined) {
      items[existingIndex] = resultItem
    } else {
      toolIndexByCallId.set(callId, items.length)
      items.push(resultItem)
    }
  }

  return items
}

export function isNearBottom(
  viewport: Pick<HTMLElement, 'scrollHeight' | 'clientHeight' | 'scrollTop'>,
  threshold = 96
) {
  const distance = viewport.scrollHeight - viewport.clientHeight - viewport.scrollTop
  return distance <= Math.max(0, threshold)
}
