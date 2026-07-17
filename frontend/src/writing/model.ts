export type WritingMode = 'polish' | 'audit'

export interface WritingHistoryRecord {
  version: 1
  id: string
  created_at: string
  mode: WritingMode
  input_text: string
  output_text: string
  options: { unicode_superscript_subscript: true }
  model: string
  input_chars: number
  output_chars: number
}

export interface WritingHistorySummary {
  version: 1
  id: string
  created_at: string
  mode: WritingMode
  input_preview: string
  model: string
  input_chars: number
  output_chars: number
}

export interface DeletedWritingHistory {
  version: 1
  trash_id: string
  deleted_at: string
  record: WritingHistorySummary
}

export interface FreshWritingTask {
  mode: WritingMode
  selectedId: null
  inputText: ''
  outputText: ''
}

export function createFreshWritingTask(mode: WritingMode): FreshWritingTask {
  return {
    mode,
    selectedId: null,
    inputText: '',
    outputText: '',
  }
}

export function modeLabel(mode: WritingMode): string {
  return mode === 'polish' ? '文字润色' : '查找漏洞'
}

export function historyPreview(text: string, maxLength = 32): string {
  const compact = text.replace(/\s+/g, ' ').trim()
  return compact.length > maxLength ? `${compact.slice(0, maxLength)}…` : compact
}

export function sortHistory<T extends { created_at: string }>(items: T[]): T[] {
  return [...items].sort((left, right) => right.created_at.localeCompare(left.created_at))
}

export function historySummary(record: WritingHistoryRecord): WritingHistorySummary {
  return {
    version: record.version,
    id: record.id,
    created_at: record.created_at,
    mode: record.mode,
    input_preview: historyPreview(record.input_text, 80),
    model: record.model,
    input_chars: record.input_chars,
    output_chars: record.output_chars,
  }
}

export function historyDate(value: string): string {
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
}
