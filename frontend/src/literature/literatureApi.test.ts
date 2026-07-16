import { describe, expect, it } from 'vitest'

import { isCompatibleLiteratureBackend, mergeWorkmodeMessages } from './literatureApi'

describe('isCompatibleLiteratureBackend', () => {
  it('rejects a generic backend or the retired proposal contract', () => {
    expect(isCompatibleLiteratureBackend({ ok: true })).toBe(false)
    expect(isCompatibleLiteratureBackend({
      ok: true,
      project_type: 'literature-library',
      tool_profile: 'literature',
      agent_tools: [
        'literature_record_propose',
        'notes_upsert_propose',
        'literature_write_confirm',
      ],
    })).toBe(false)
  })

  it('accepts a specialized Workmode project with direct literature tools', () => {
    expect(isCompatibleLiteratureBackend({
      ok: true,
      project_type: 'literature-library',
      tool_profile: 'literature',
      agent_tools: [
        'literature_search',
        'literature_tag_list',
        'literature_read',
        'literature_update_record',
        'literature_delete',
        'literature_restore',
        'literature_note_upsert',
        'literature_note_delete',
      ],
    })).toBe(true)
  })

  it('keeps imported and selected literature system events in the visible timeline', () => {
    const messages = mergeWorkmodeMessages([
      {
        id: 'import-1',
        role: 'system',
        content: '用户刚刚导入了以下文献：\n- source.pdf',
        ts: '2026-07-15T00:00:00Z',
        meta: {
          event: 'literature_import_confirmed',
          paper_ids: ['paper-1'],
        },
      },
      {
        id: 'selection-1',
        role: 'system',
        content: '用户当前选择了以下文献：\n- source.pdf',
        ts: '2026-07-15T00:00:01Z',
        meta: {
          event: 'literature_selection_changed',
          paper_ids: ['paper-1'],
        },
      },
      {
        id: 'user-1',
        role: 'user',
        content: '介绍一下',
        ts: '2026-07-15T00:00:02Z',
        meta: { active_context: [{ kind: 'paper', id: 'paper-1' }] },
      },
    ])

    expect(messages.map((message) => message.role)).toEqual(['system', 'system', 'user'])
    expect(messages[0]).toMatchObject({
      content: '用户刚刚导入了以下文献：\n- source.pdf',
      paper_ids: ['paper-1'],
    })
    expect(messages[1]).toMatchObject({
      content: '用户当前选择了以下文献：\n- source.pdf',
      paper_ids: ['paper-1'],
    })
  })

  it('hides an imported event until the next user message exists', () => {
    const messages = mergeWorkmodeMessages([
      {
        id: 'import-pending',
        role: 'system',
        content: '用户刚刚导入了以下文献：\n- pending.pdf',
        ts: '2026-07-15T00:00:00Z',
        meta: {
          event: 'literature_import_confirmed',
          paper_ids: ['paper-pending'],
        },
      },
    ])

    expect(messages).toEqual([])
  })
})
