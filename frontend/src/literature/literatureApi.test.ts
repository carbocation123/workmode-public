import { describe, expect, it } from 'vitest'

import { isCompatibleLiteratureBackend } from './literatureApi'

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
        'literature_note_upsert',
      ],
    })).toBe(true)
  })
})
