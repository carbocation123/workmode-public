import type { FileEntry } from './api'

function ancestorDirectories(path: string) {
  const parts = path.split('/').filter(Boolean)
  const ancestors: string[] = []
  for (let index = 1; index < parts.length; index += 1) {
    ancestors.push(parts.slice(0, index).join('/'))
  }
  return ancestors
}

export function directoryPaths(entries: FileEntry[]) {
  return new Set(entries.filter((entry) => entry.kind === 'dir').map((entry) => entry.path))
}

export function visibleFileEntries(entries: FileEntry[], expandedDirectories: ReadonlySet<string>) {
  return entries.filter((entry) => (
    ancestorDirectories(entry.path).every((path) => expandedDirectories.has(path))
  ))
}
