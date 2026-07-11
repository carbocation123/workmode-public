import { describe, expect, it } from 'vitest'
import type { FileEntry } from './api'
import { directoryPaths, fileEntryVisual, visibleFileEntries } from './fileTree'

const entries: FileEntry[] = [
  { path: 'alpha', name: 'alpha', kind: 'dir', size: 0, preview: 'unsupported' },
  { path: 'alpha/nested', name: 'nested', kind: 'dir', size: 0, preview: 'unsupported' },
  { path: 'alpha/nested/paper.pdf', name: 'paper.pdf', kind: 'file', size: 12, preview: 'media' },
  { path: 'alpha/readme.md', name: 'readme.md', kind: 'file', size: 12, preview: 'text' },
  { path: 'root.txt', name: 'root.txt', kind: 'file', size: 4, preview: 'text' }
]

describe('visibleFileEntries', () => {
  it('hides descendants of collapsed directories but keeps later root entries visible', () => {
    expect(visibleFileEntries(entries, new Set()).map((entry) => entry.path)).toEqual([
      'alpha',
      'root.txt'
    ])

    expect(visibleFileEntries(entries, new Set(['alpha'])).map((entry) => entry.path)).toEqual([
      'alpha',
      'alpha/nested',
      'alpha/readme.md',
      'root.txt'
    ])
  })

  it('lists every directory path so refreshed trees can preserve valid expansion state', () => {
    expect(directoryPaths(entries)).toEqual(new Set(['alpha', 'alpha/nested']))
  })

  it('uses recognizable icons and labels for common research files', () => {
    expect(fileEntryVisual(entries[0], false)).toEqual({ icon: '📁', label: '文件夹' })
    expect(fileEntryVisual(entries[0], true)).toEqual({ icon: '📂', label: '已展开文件夹' })
    expect(fileEntryVisual(entries[2], false)).toEqual({ icon: '📕', label: 'PDF' })
    expect(fileEntryVisual(entries[3], false)).toEqual({ icon: '📝', label: 'Markdown' })
    expect(fileEntryVisual({ path: 'data/run.csv', name: 'run.csv', kind: 'file', size: 4, preview: 'text' }, false)).toEqual({ icon: '📊', label: '数据' })
    expect(fileEntryVisual({ path: 'scripts/analyze.py', name: 'analyze.py', kind: 'file', size: 4, preview: 'text' }, false)).toEqual({ icon: '⌘', label: '代码' })
  })
})
