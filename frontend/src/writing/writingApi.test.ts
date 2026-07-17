import { afterEach, describe, expect, it, vi } from 'vitest'

import { setApiBase } from '../api'
import { deleteHistory, listHistory, processText, restoreHistory } from './writingApi'


afterEach(() => {
  vi.unstubAllGlobals()
  localStorage.clear()
})


describe('article processing API client', () => {
  it('sends the selected mode and exact input text', async () => {
    setApiBase('http://127.0.0.1:9999/api')
    const response = {
      record: {
        version: 1,
        id: 'abc',
        created_at: '2026-01-01T00:00:00Z',
        mode: 'polish',
        input_text: ' H2O ',
        output_text: ' H₂O ',
        options: { unicode_superscript_subscript: true },
        model: 'test-model',
        input_chars: 5,
        output_chars: 5,
      },
    }
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => response })
    vi.stubGlobal('fetch', fetchMock)

    const record = await processText('polish', ' H2O ')

    expect(record.output_text).toBe(' H₂O ')
    expect(fetchMock).toHaveBeenCalledWith(
      'http://127.0.0.1:9999/api/writing/process',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ mode: 'polish', input_text: ' H2O ' }),
      }),
    )
  })

  it('uses recoverable delete and restore endpoints', async () => {
    setApiBase('http://127.0.0.1:9999/api')
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => ({ items: [] }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ trash: { trash_id: 'trash' } }) })
      .mockResolvedValueOnce({ ok: true, json: async () => ({ record: { id: 'restored' } }) })
    vi.stubGlobal('fetch', fetchMock)

    expect(await listHistory()).toEqual([])
    expect((await deleteHistory('active')).trash_id).toBe('trash')
    expect((await restoreHistory('trash')).id).toBe('restored')
    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      'http://127.0.0.1:9999/api/writing/history',
      'http://127.0.0.1:9999/api/writing/history/active',
      'http://127.0.0.1:9999/api/writing/trash/trash/restore',
    ])
  })
})
