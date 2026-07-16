export type PaperStatus =
  | 'pending'
  | 'parsing'
  | 'extracting'
  | 'review'
  | 'ready'
  | 'failed'

export type TagCategory =
  | 'characterization'
  | 'material'
  | 'mechanism'
  | 'performance'
  | 'uncategorized'

export type PaperType = 'research' | 'review' | 'unknown'
export type MetadataSource = 'cite_this' | 'layout_json_fallback' | 'manual_review' | 'pending'
export type ArchiveLocation = '文献/未处理' | '文献/已处理'
export type VerificationStatus = 'pending' | 'passed' | 'needs_fix'

export interface TagDefinition {
  id: string
  name: string
  aliases: string[]
  category: TagCategory
  status: 'confirmed' | 'provisional'
}

export interface FactReportEntry {
  kind: 'metadata' | 'method' | 'data' | 'observation' | 'author_interpretation' | 'excerpt'
  content: string
  location?: string
}

export interface FactReportSection {
  id: string
  title: string
  owner: 'extractor' | 'main_conversation'
  entries: FactReportEntry[]
}

export interface PaperRecord {
  id: string
  filename: string
  pdfPath: string | null
  archiveFilename: string | null
  archiveLocation: ArchiveLocation
  metadataSource: MetadataSource
  paperType: PaperType
  verificationStatus: VerificationStatus
  title: string
  authors: string
  year: number | null
  journal: string
  status: PaperStatus
  tagIds: string[]
  focus: string
  summary: string
  facts: string[]
  factReport: FactReportSection[]
  metadataTrust: 'complete' | 'partial' | 'unknown'
  metadataIssue: string
}

export interface ProjectMemoryState {
  projectMemory: string[]
}

const NEXT_STATUS: Record<PaperStatus, PaperStatus> = {
  pending: 'parsing',
  parsing: 'extracting',
  extracting: 'review',
  review: 'ready',
  ready: 'ready',
  failed: 'failed',
}

function normalize(value: string): string {
  return value.trim().toLocaleLowerCase().replace(/[\s_-]+/g, '')
}

function titleFromFilename(filename: string): string {
  return filename
    .replace(/\.pdf$/i, '')
    .replace(/[_-]+/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function stablePaperId(filename: string, index: number): string {
  const slug = titleFromFilename(filename)
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, '-')
    .replace(/(^-|-$)/g, '')
    .slice(0, 36)
  return `import-${slug || 'paper'}-${index + 1}`
}

export function createImportedPapers(filenames: string[]): PaperRecord[] {
  return filenames
    .filter((filename) => filename.toLocaleLowerCase().endsWith('.pdf'))
    .map((filename, index) => ({
      id: stablePaperId(filename, index),
      filename,
      pdfPath: null,
      archiveFilename: null,
      archiveLocation: '文献/未处理' as const,
      metadataSource: 'pending' as const,
      paperType: 'unknown' as const,
      verificationStatus: 'pending' as const,
      title: titleFromFilename(filename),
      authors: '等待元数据识别',
      year: null,
      journal: '等待元数据识别',
      status: 'pending' as const,
      tagIds: [],
      focus: '',
      summary: '',
      facts: [],
      factReport: [],
      metadataTrust: 'unknown' as const,
      metadataIssue: '',
    }))
}

export function progressPaper(paper: PaperRecord): PaperRecord {
  return { ...paper, status: NEXT_STATUS[paper.status] }
}

export function attachPapers(current: string[], additions: string[]): string[] {
  return [...new Set([...current, ...additions])]
}

export function normalizeSuggestedTag(
  suggestion: string,
  registry: TagDefinition[],
): TagDefinition {
  const normalizedSuggestion = normalize(suggestion)
  const existing = registry.find(
    (tag) =>
      normalize(tag.name) === normalizedSuggestion ||
      tag.aliases.some((alias) => normalize(alias) === normalizedSuggestion),
  )
  if (existing) return existing

  const id = suggestion
    .trim()
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, '_')
    .replace(/(^_|_$)/g, '')

  return {
    id: id || `tag_${registry.length + 1}`,
    name: suggestion.trim(),
    aliases: [],
    category: 'uncategorized',
    status: 'provisional',
  }
}

export function filterPapersByTagIds<T extends { tagIds: string[] }>(
  papers: T[],
  selectedTagIds: string[],
): T[] {
  if (!selectedTagIds.length) return papers
  return papers.filter((paper) => selectedTagIds.every((tagId) => paper.tagIds.includes(tagId)))
}

export function buildArchiveFilename(
  firstAuthorSurname: string,
  year: number,
  journalAbbreviation: string,
): string | null {
  const surname = firstAuthorSurname.trim()
  const journal = journalAbbreviation.trim()
  if (!/^\p{L}[\p{L}'-]*$/u.test(surname)) return null
  if (!Number.isInteger(year) || year < 1800 || year > 2100) return null
  if (!/^[A-Z][A-Za-z0-9]*$/.test(journal)) return null
  return `${surname}_${year}_${journal}.pdf`
}

export function resolveArchiveFilenameCollision(
  candidate: string,
  existingFilenames: string[],
): string {
  const occupied = new Set(existingFilenames.map((filename) => filename.toLocaleLowerCase()))
  if (!occupied.has(candidate.toLocaleLowerCase())) return candidate

  const stem = candidate.replace(/\.pdf$/i, '')
  let sequence = 2
  while (occupied.has(`${stem}_${sequence}.pdf`.toLocaleLowerCase())) sequence += 1
  return `${stem}_${sequence}.pdf`
}

export function resolveNoteFilename(title: string, existingFilenames: string[]): string {
  const safeStem = title
    .trim()
    .replace(/[<>:"/\\|?*：]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/[. ]+$/g, '') || '未命名笔记'
  const occupied = new Set(existingFilenames.map((filename) => filename.toLocaleLowerCase()))
  const candidate = `${safeStem}.md`
  if (!occupied.has(candidate.toLocaleLowerCase())) return candidate

  let sequence = 2
  while (occupied.has(`${safeStem}_${sequence}.md`.toLocaleLowerCase())) sequence += 1
  return `${safeStem}_${sequence}.md`
}

export function sectionsWritableByExtractor<T extends Pick<FactReportSection, 'owner'>>(
  sections: T[],
): T[] {
  return sections.filter((section) => section.owner === 'extractor')
}

export function updateSessionById<T extends { id: string }>(
  sessions: T[],
  sessionId: string,
  updater: (session: T) => T,
): T[] {
  return sessions.map((session) => (session.id === sessionId ? updater(session) : session))
}

export function statusLabel(status: PaperStatus): string {
  return {
    pending: '待处理',
    parsing: '正在解析正文',
    extracting: '正在提取事实',
    review: '待讨论',
    ready: '已整理',
    failed: '处理失败',
  }[status]
}
