import { describe, expect, it } from 'vitest'

import { isCompatibleLiteratureBackend, mapBackendPaper, mergeWorkmodeMessages } from './literatureApi'

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

describe('mapBackendPaper', () => {
  it('preserves the useful bibliographic, organization, asset and workflow fields shown to AI', () => {
    const paper = mapBackendPaper({
      id: 'paper-1',
      original_filename: 'source.pdf',
      archive_filename: 'Zhang_2024_NatCatal.pdf',
      archive_location: '文献/未处理',
      title: 'Catalyst paper',
      authors: 'Zhang, San',
      first_author_surname: 'Zhang',
      year: 2024,
      publication_date: '2024-05-10',
      journal: 'Nature Catalysis',
      journal_abbreviation: 'NatCatal',
      doi: '10.1000/example',
      status: 'extracting',
      tags: ['xps'],
      group_ids: ['doctoral'],
      focus: '界面结构',
      summary: '关注构效关系。',
      paper_type: 'research',
      metadata_source: 'manual_review',
      metadata_trust: 'complete',
      metadata_issue: '',
      verification_status: 'pending',
      stage: 'extracting_facts',
      error: 'one page needs review',
      paths: {
        pdf: 'papers/unprocessed/pdf/source.pdf',
        si_folder: 'papers/unprocessed/SI/paper-1',
        mineru_dir: 'papers/unprocessed/extracted/paper-1',
        full_md: 'papers/unprocessed/extracted/paper-1/full.md',
        fact_report: 'papers/unprocessed/extracted/paper-1/facts.md',
      },
    })

    expect(paper).toMatchObject({
      firstAuthorSurname: 'Zhang',
      journalAbbreviation: 'NatCatal',
      doi: '10.1000/example',
      processingStage: 'extracting_facts',
      processingError: 'one page needs review',
      groupIds: ['doctoral'],
      tagIds: ['xps'],
      siFolder: 'papers/unprocessed/SI/paper-1',
    })
  })
})
