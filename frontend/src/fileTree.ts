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

export function fileEntryVisual(entry: FileEntry, expanded: boolean) {
  if (entry.kind === 'dir') {
    return expanded
      ? { icon: '📂', label: '已展开文件夹', slot: 'folder-open' as const }
      : { icon: '📁', label: '文件夹', slot: 'folder' as const }
  }

  const extension = entry.name.toLowerCase().split('.').pop() || ''
  if (extension === 'md' || extension === 'mdx') return { icon: '📝', label: 'Markdown', slot: 'markdown' as const }
  if (extension === 'pdf') return { icon: '📕', label: 'PDF', slot: 'pdf' as const }
  if (['png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp', 'svg'].includes(extension)) return { icon: '🖼️', label: '图片', slot: 'image' as const }
  if (['py', 'js', 'jsx', 'ts', 'tsx', 'rs', 'c', 'cc', 'cpp', 'h', 'hpp', 'java', 'kt', 'r', 'sh', 'ps1', 'bat', 'cmd'].includes(extension)) return { icon: '⌘', label: '代码', slot: 'code' as const }
  if (['csv', 'tsv', 'xls', 'xlsx', 'dat', 'spc', 'par', 'asc', 'jsonl'].includes(extension)) return { icon: '📊', label: '数据', slot: 'data' as const }
  if (['zip', '7z', 'rar', 'tar', 'gz'].includes(extension)) return { icon: '📦', label: '压缩包', slot: 'archive' as const }
  if (entry.preview === 'text') return { icon: '📄', label: '文本', slot: 'text' as const }
  if (entry.preview === 'media') return { icon: '◇', label: '媒体', slot: 'media' as const }
  return { icon: '·', label: '文件', slot: 'file' as const }
}

export function visibleFileEntries(entries: FileEntry[], expandedDirectories: ReadonlySet<string>) {
  return entries.filter((entry) => (
    ancestorDirectories(entry.path).every((path) => expandedDirectories.has(path))
  ))
}
