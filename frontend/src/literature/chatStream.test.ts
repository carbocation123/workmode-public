import { describe, expect, it } from 'vitest'

import {
  chatActionMessageForEvent,
  createLiveChatState,
  reduceLiveChatEvent,
  type LiteratureChatMessage,
} from './chatStream'

describe('literature live chat timeline', () => {
  it('keeps text, one live tool card, and later text in real stream order', () => {
    const initial: LiteratureChatMessage[] = [{
      id: 'local-user',
      role: 'user',
      text: '处理这篇文献',
    }]
    let state = createLiveChatState(initial, 'run-1', 12)

    state = reduceLiveChatEvent(state, { type: 'text_delta', content: '我先读取记录。' })
    state = reduceLiveChatEvent(state, {
      type: 'tool_call_start',
      id: 'call-1',
      name: 'literature_read',
      input: { paper_id: 'paper-1' },
      message: {
        id: 'tool-start',
        role: 'tool',
        content: '调用 literature_read',
        ts: '2026-07-13T00:00:00Z',
        meta: {
          event: 'tool_call_start',
          tool_call_id: 'call-1',
          tool_name: 'literature_read',
          args: { paper_id: 'paper-1' },
          status: 'running',
        },
      },
    })
    state = reduceLiveChatEvent(state, {
      type: 'tool_result',
      id: 'call-1',
      name: 'literature_read',
      ok: true,
      result: '{"title":"Example"}',
      message: {
        id: 'tool-result',
        role: 'tool',
        content: '{"title":"Example"}',
        ts: '2026-07-13T00:00:01Z',
        meta: {
          event: 'tool_result',
          tool_call_id: 'call-1',
          tool_name: 'literature_read',
          status: 'done',
          ok: true,
        },
      },
    })
    state = reduceLiveChatEvent(state, { type: 'text_delta', content: '读取完成，下面讨论结论。' })

    expect(state.messages.map((message) => message.role)).toEqual([
      'user',
      'assistant',
      'tool',
      'assistant',
    ])
    expect(state.messages[1].text).toBe('我先读取记录。')
    expect(state.messages[2]).toMatchObject({
      toolCallId: 'call-1',
      toolName: 'literature_read',
      toolStatus: 'completed',
      text: '{"title":"Example"}',
    })
    expect(state.messages[3].text).toBe('读取完成，下面讨论结论。')
  })

  it('updates context usage without inserting a fake chat message', () => {
    let state = createLiveChatState([], 'run-2', 0)
    state = reduceLiveChatEvent(state, {
      type: 'context_usage',
      context: { budget_tokens: 1000, prompt_tokens_estimate: 250 },
    })

    expect(state.contextPercent).toBe(25)
    expect(state.messages).toEqual([])
  })

  it('inserts persisted system context before the optimistic user message', () => {
    let state = createLiveChatState([{
      id: 'local-user',
      role: 'user',
      text: '介绍一下',
    }], 'run-system', 0)

    state = reduceLiveChatEvent(state, {
      type: 'system_message',
      message: {
        id: 'selection-event',
        role: 'system',
        content: '用户当前选择了以下文献：\n- source.pdf',
        ts: '2026-07-15T00:00:00Z',
        meta: {
          event: 'literature_selection_changed',
          paper_ids: ['paper-1'],
        },
      },
    })

    expect(state.messages.map((message) => message.role)).toEqual(['system', 'user'])
    expect(state.messages[0]).toMatchObject({
      text: '用户当前选择了以下文献：\n- source.pdf',
      paperIds: ['paper-1'],
    })
  })

  it('clears the transient next-round notice when the turn finishes', () => {
    const continuing = chatActionMessageForEvent('', { type: 'loop_continue', round: 2 })
    const finished = chatActionMessageForEvent(continuing, { type: 'done' })

    expect(continuing).toBe('工具调用完成，继续生成第 2 轮…')
    expect(finished).toBe('')
  })
})
