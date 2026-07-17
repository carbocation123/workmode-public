import { describe, expect, it } from 'vitest'

import { createFreshWritingTask, historyPreview, modeLabel, sortHistory, type WritingHistoryRecord } from './model'

function record(id: string, createdAt: string, inputText: string): WritingHistoryRecord {
  return {
    version: 1,
    id,
    created_at: createdAt,
    mode: 'polish',
    input_text: inputText,
    output_text: '输出',
    options: { unicode_superscript_subscript: true },
    model: 'test-model',
    input_chars: inputText.length,
    output_chars: 2,
  }
}

describe('article processing view model', () => {
  it('sorts newest history first without mutating the API array', () => {
    const items = [record('old', '2026-01-01T00:00:00Z', '旧'), record('new', '2026-02-01T00:00:00Z', '新')]
    expect(sortHistory(items).map((item) => item.id)).toEqual(['new', 'old'])
    expect(items.map((item) => item.id)).toEqual(['old', 'new'])
  })

  it('builds compact single-line previews and human mode labels', () => {
    expect(historyPreview('  第一行\n\n第二行  ', 8)).toBe('第一行 第二行')
    expect(historyPreview('这是一段非常非常长的文字', 6)).toBe('这是一段非常…')
    expect(modeLabel('polish')).toBe('文字润色')
    expect(modeLabel('audit')).toBe('查找漏洞')
  })

  it('starts a blank task without changing the selected processing mode', () => {
    expect(createFreshWritingTask('audit')).toEqual({
      mode: 'audit',
      selectedId: null,
      inputText: '',
      outputText: '',
    })
  })
})
