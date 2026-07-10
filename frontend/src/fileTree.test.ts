import { describe, expect, it } from 'vitest'
import type { FileEntry } from './api'
import { directoryPaths, visibleFileEntries } from './fileTree'

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

  it('lists every directory path for the default expanded state', () => {
    expect(directoryPaths(entries)).toEqual(new Set(['alpha', 'alpha/nested']))
  })
})
