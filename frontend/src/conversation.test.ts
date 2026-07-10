import { describe, expect, it } from 'vitest'
import type { Message } from './api'
import { buildConversationItems, isNearBottom } from './conversation'

function message(id: string, role: Message['role'], content: string, meta: Record<string, unknown> = {}): Message {
  return { id, role, content, meta, ts: '2026-07-10T00:00:00Z' }
}

describe('buildConversationItems', () => {
  it('merges tool start and result events into one item in the original position', () => {
    const messages = [
      message('u1', 'user', 'read it'),
      message('t1', 'tool', '调用 project_read…', {
        event: 'tool_call_start',
        tool_call_id: 'call-1',
        tool_name: 'project_read',
        args: { path: 'notes.md' },
        status: 'running'
      }),
      message('t2', 'tool', '1\thello', {
        event: 'tool_result',
        tool_call_id: 'call-1',
        tool_name: 'project_read',
        status: 'done',
        changed_paths: []
      }),
      message('a1', 'assistant', 'done')
    ]

    const items = buildConversationItems(messages)

    expect(items).toHaveLength(3)
    expect(items[1]).toMatchObject({
      kind: 'tool',
      callId: 'call-1',
      toolName: 'project_read',
      status: 'done',
      args: { path: 'notes.md' },
      result: '1\thello'
    })
  })

  it('keeps an unfinished tool call as one running item', () => {
    const items = buildConversationItems([
      message('t1', 'tool', '调用 web_search…', {
        event: 'tool_call_start',
        tool_call_id: 'call-2',
        tool_name: 'web_search',
        args: { queries: ['a', 'b'] },
        status: 'running'
      })
    ])

    expect(items).toEqual([
      expect.objectContaining({ kind: 'tool', callId: 'call-2', status: 'running', result: '' })
    ])
  })

  it('marks an unfinished persisted tool as cancelled after streaming stops', () => {
    const items = buildConversationItems([
      message('t1', 'tool', 'calling web_search', {
        event: 'tool_call_start',
        tool_call_id: 'call-stopped',
        tool_name: 'web_search',
        args: { query: 'paper' },
        status: 'running'
      })
    ], 'cancelled')

    expect(items).toEqual([
      expect.objectContaining({ kind: 'tool', callId: 'call-stopped', status: 'cancelled' })
    ])
  })

  it('renders an orphan result without inventing a running card', () => {
    const items = buildConversationItems([
      message('t2', 'tool', 'network failed', {
        event: 'tool_result',
        tool_call_id: 'call-3',
        tool_name: 'web_fetch',
        status: 'error'
      })
    ])

    expect(items).toEqual([
      expect.objectContaining({ kind: 'tool', callId: 'call-3', status: 'error', result: 'network failed' })
    ])
  })

  it('preserves interleaved text and tools and marks a stopped tool as cancelled', () => {
    const items = buildConversationItems([
      message('u1', 'user', 'research it'),
      message('a1', 'assistant', 'first note'),
      message('t1', 'tool', 'calling web_search', {
        event: 'tool_call_start',
        tool_call_id: 'call-4',
        tool_name: 'web_search',
        status: 'running'
      }),
      message('t2', 'tool', 'found', {
        event: 'tool_result',
        tool_call_id: 'call-4',
        tool_name: 'web_search',
        status: 'done'
      }),
      message('a2', 'assistant', 'second note'),
      message('t3', 'tool', 'calling web_fetch', {
        event: 'tool_call_start',
        tool_call_id: 'call-5',
        tool_name: 'web_fetch',
        status: 'running'
      }),
      message('t4', 'tool', 'stopped by user', {
        event: 'tool_result',
        tool_call_id: 'call-5',
        tool_name: 'web_fetch',
        status: 'cancelled'
      })
    ])

    expect(items.map((item) => item.kind === 'tool' ? `${item.toolName}:${item.status}` : item.message.content)).toEqual([
      'research it',
      'first note',
      'web_search:done',
      'second note',
      'web_fetch:cancelled'
    ])
  })
})

describe('isNearBottom', () => {
  it('uses a bounded distance threshold for auto-follow', () => {
    expect(isNearBottom({ scrollHeight: 1000, clientHeight: 400, scrollTop: 540 }, 80)).toBe(true)
    expect(isNearBottom({ scrollHeight: 1000, clientHeight: 400, scrollTop: 450 }, 80)).toBe(false)
  })
})
