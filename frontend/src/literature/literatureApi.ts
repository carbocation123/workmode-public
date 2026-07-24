import type { FactReportSection, PaperRecord } from './model'
import { LITERATURE_PROJECT_KEY, RUNTIME_API_BASE_KEY } from '../literatureNavigation'
import { api, streamChat, type ChatStreamEvent } from '../api'

const DEFAULT_API_ROOT = 'http://127.0.0.1:8765/api'
const cachedApiRoot = typeof window !== 'undefined'
  ? window.sessionStorage.getItem(RUNTIME_API_BASE_KEY)
  : null
export const WORKMODE_API_ROOT = (
  cachedApiRoot || import.meta.env.VITE_WORKMODE_API_BASE || DEFAULT_API_ROOT
).replace(/\/$/, '')

export interface WorkmodeProject {
  slug: string
  name: string
  root_path: string
  project_type?: string
  tool_profile?: string
  storage_mode?: 'managed' | 'external'
}

interface WorkmodeMessage {
  id: string
  role: 'assistant' | 'user' | 'system' | 'tool'
  content: string
  ts?: string
  meta?: {
    event?: string
    tool_call_id?: string
    tool_name?: string
    args?: Record<string, unknown>
    status?: string
    ok?: boolean
    active_context?: Array<{ kind: 'paper' | 'note'; id: string }>
    paper_ids?: string[]
  }
}

interface WorkmodeSessionMeta {
  id: string
  title: string
  project_slug: string
  created_at: string
  updated_at: string
}

export interface LiteratureBackendHealth {
  ok: boolean
  project_slug?: string
  project_type?: string
  schema_version?: number
  tool_profile?: string
  agent_tools?: string[]
}

const REQUIRED_AGENT_TOOLS = [
  'literature_search',
  'literature_library_overview',
  'literature_tag_list',
  'literature_read',
  'literature_update_record',
  'literature_delete',
  'literature_restore',
  'literature_note_upsert',
  'literature_note_delete',
]

export function isCompatibleLiteratureBackend(health: LiteratureBackendHealth): boolean {
  const tools = new Set(health.agent_tools || [])
  return Boolean(
    health.ok
    && health.project_type === 'literature-library'
    && health.tool_profile === 'literature'
    && REQUIRED_AGENT_TOOLS.every((name) => tools.has(name)),
  )
}

interface WorkmodeContextUsage {
  budget_tokens?: number
  prompt_tokens_estimate?: number
}

export interface BackendPaper {
  id: string
  original_filename: string
  archive_filename: string | null
  archive_location: '文献/未处理' | '文献/已处理'
  title: string
  authors: string
  first_author_surname?: string
  year: number | null
  publication_date?: string
  journal: string
  journal_abbreviation?: string
  doi?: string
  status: PaperRecord['status']
  tags: string[]
  group_ids?: string[]
  focus: string
  summary: string
  paper_type: PaperRecord['paperType']
  metadata_source: PaperRecord['metadataSource'] | 'manual' | 'layout_json'
  metadata_trust: PaperRecord['metadataTrust'] | 'pending'
  metadata_issue?: string | null
  mineru_output_path?: string | null
  fact_report_path?: string | null
  stage?: string
  error?: string | null
  verification_status?: PaperRecord['verificationStatus']
  paths?: { pdf?: string; si_folder?: string; mineru_dir?: string; full_md?: string; fact_report?: string }
}

interface CatalogPaper {
  id: string
  original_filename?: string
  archive_filename?: string | null
  archive_location?: string
  title?: string
  authors?: string
  first_author_surname?: string
  year?: number | null
  publication_date?: string
  journal?: string
  journal_abbreviation?: string
  doi?: string
  status?: PaperRecord['status']
  tag_ids?: string[]
  group_ids?: string[]
  focus?: string
  summary?: string
  paper_type?: PaperRecord['paperType']
  metadata_source?: string
  metadata_trust?: PaperRecord['metadataTrust'] | 'pending'
  metadata_issue?: string | null
  verification_status?: PaperRecord['verificationStatus']
  stage?: string
  error?: string | null
  paths?: { pdf?: string; si_folder?: string; mineru_dir?: string; full_md?: string; fact_report?: string }
}

interface ImportResult {
  paper: CatalogPaper
  duplicate: boolean
}

export interface BackendChatMessage {
  id: string
  role: 'assistant' | 'user' | 'system' | 'tool'
  content: string
  paper_ids?: string[]
  note_ids?: string[]
  tool_call_id?: string
  tool_name?: string
  tool_args?: Record<string, unknown>
  tool_status?: 'running' | 'completed' | 'failed' | 'cancelled'
  created_at?: string
}

export interface BackendSession {
  id: string
  name: string
  messages: BackendChatMessage[]
  attached_paper_ids: string[]
  attached_note_ids: string[]
  created_at: string
  updated_at: string
  context_percent: number
}

export interface BackendTag {
  id: string
  name: string
  aliases: string[]
  group_id: string
  status: 'confirmed' | 'provisional'
}

export interface BackendTagGroup {
  id: string
  name: string
  color: string
  order: number
}

export interface BackendLiteratureGroup {
  id: string
  name: string
}

export interface EndNoteLibraryCandidate {
  path: string
  name: string
  type: 'enl' | 'enlx'
  size: number
  modified_at: number
  has_data_folder: boolean
  recommended_reason:
    | 'complete_working_library'
    | 'compressed_library'
    | 'library_without_data_folder'
  variants: Array<{
    path: string
    name: string
    type: 'enl' | 'enlx'
    size: number
    modified_at: number
  }>
}

export interface EndNotePreview {
  source_path: string
  source_type: 'enl' | 'enlx'
  reference_count: number
  attachment_count: number
  manual_group_count: number
  tag_count: number
  importable_count: number
  failed_count: number
  failures: Array<{ endnote_record_id: number; title: string; reason: string }>
}

export interface EndNoteImportResult {
  ok: boolean
  imported_count: number
  failed_count: number
  group_count: number
  tag_count: number
  paper_ids: string[]
  failures: EndNotePreview['failures']
}

export interface DuplicateScanResult {
  ok: boolean
  group_count: number
  groups: Array<{
    paper_ids: string[]
    reasons: Array<'doi' | 'main_pdf_sha256' | 'title_year_first_author'>
    confidence: 'exact' | 'possible'
  }>
}

export interface BackendNote {
  id: string
  filename: string
  title: string
  markdown: string
  source_paper_ids: string[]
  updated_at: string
}

export interface ArchiveVerification {
  ok: boolean
  paper_id: string
  issues: string[]
}

export interface DeletedBackendPaper {
  trash_id: string
  deleted_at: string
  paper: BackendPaper
  file_count: number
}

let activeProject: WorkmodeProject | null = null

function authHeaders(extra?: HeadersInit): HeadersInit {
  const token = localStorage.getItem('workmode-public-token') || ''
  return {
    ...(token ? { 'X-Workmode-Token': token } : {}),
    ...(extra || {}),
  }
}

async function rawRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${WORKMODE_API_ROOT}${path}`, {
    ...init,
    headers: authHeaders(init?.headers),
  })
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = await response.json() as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
      else if (body.detail) detail = JSON.stringify(body.detail)
    } catch {
      // Keep the HTTP status when the body is not JSON.
    }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

async function resolveProject(): Promise<WorkmodeProject> {
  if (activeProject) return activeProject
  const result = await rawRequest<{ projects: WorkmodeProject[] }>('/work/projects')
  const requestedSlug = String(
    (typeof window !== 'undefined' ? window.sessionStorage.getItem(LITERATURE_PROJECT_KEY) : '')
    || import.meta.env.VITE_LITERATURE_PROJECT_SLUG
    || '',
  ).trim()
  const literatureProjects = result.projects.filter((item) => item.project_type === 'literature-library')
  const project = literatureProjects.find((item) => item.slug === requestedSlug) || literatureProjects[0]
  if (!project) {
    throw new Error('没有已注册的 literature-library 项目。请先创建文献项目。')
  }
  activeProject = project
  return project
}

export async function listBackendLiteratureProjects(): Promise<WorkmodeProject[]> {
  const result = await api.projects()
  return result.projects.filter((project) => project.project_type === 'literature-library')
}

export async function createBackendLiteratureProject(name: string): Promise<WorkmodeProject> {
  const result = await api.createLiteratureProject({ name })
  activeProject = result.project
  window.sessionStorage.setItem(LITERATURE_PROJECT_KEY, result.project.slug)
  return result.project
}

export async function activateBackendLiteratureProject(slug: string): Promise<void> {
  await api.setActive(slug)
  activeProject = null
  window.sessionStorage.setItem(LITERATURE_PROJECT_KEY, slug)
}

export async function renameBackendProject(slug: string, name: string): Promise<WorkmodeProject> {
  const result = await api.updateProject(slug, { name })
  if (activeProject?.slug === slug) activeProject = result.project
  return result.project
}

export async function removeBackendProject(slug: string): Promise<void> {
  await api.deleteProject(slug)
  if (activeProject?.slug === slug) activeProject = null
}

export async function getBackendProjectInfo(): Promise<WorkmodeProject> {
  return resolveProject()
}

async function literatureRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const project = await resolveProject()
  return rawRequest<T>(`/work/projects/${encodeURIComponent(project.slug)}/literature${path}`, init)
}

function fromCatalogPaper(paper: CatalogPaper): BackendPaper {
  const source = paper.metadata_source === 'layout_json'
    ? 'layout_json_fallback'
    : paper.metadata_source === 'manual'
      ? 'manual_review'
      : paper.metadata_source
  return {
    id: paper.id,
    original_filename: paper.original_filename || `${paper.id}.pdf`,
    archive_filename: paper.archive_filename || null,
    archive_location: paper.archive_location === 'papers/processed' ? '文献/已处理' : '文献/未处理',
    title: paper.title || '',
    authors: paper.authors || '',
    first_author_surname: paper.first_author_surname || '',
    year: paper.year ?? null,
    publication_date: paper.publication_date || '',
    journal: paper.journal || '',
    journal_abbreviation: paper.journal_abbreviation || '',
    doi: paper.doi || '',
    status: paper.status || 'pending',
    tags: paper.tag_ids || [],
    group_ids: paper.group_ids || [],
    focus: paper.focus || '',
    summary: paper.summary || '',
    paper_type: paper.paper_type || 'research',
    metadata_source: (source || 'pending') as PaperRecord['metadataSource'],
    metadata_trust: paper.metadata_trust || 'unknown',
    metadata_issue: paper.metadata_issue || '',
    mineru_output_path: paper.paths?.mineru_dir || null,
    fact_report_path: paper.paths?.fact_report || null,
    paths: paper.paths,
    stage: paper.stage,
    error: paper.error,
    verification_status: paper.verification_status || 'pending',
  }
}

export function mergeWorkmodeMessages(messages: WorkmodeMessage[]): BackendChatMessage[] {
  const starts = new Map<string, WorkmodeMessage>()
  const output: BackendChatMessage[] = []
  for (const [index, message] of messages.entries()) {
    const meta = message.meta || {}
    if (
      message.role === 'system'
      && meta.event === 'literature_import_confirmed'
      && !messages.slice(index + 1).some((later) => later.role === 'user')
    ) {
      continue
    }
    if (message.role === 'tool' && meta.event === 'tool_call_start' && meta.tool_call_id) {
      starts.set(meta.tool_call_id, message)
      continue
    }
    if (message.role === 'tool' && meta.event === 'tool_result' && meta.tool_call_id) {
      const start = starts.get(meta.tool_call_id)
      starts.delete(meta.tool_call_id)
      const persistedStatus = meta.status === 'cancelled'
        ? 'cancelled'
        : meta.status === 'running'
          ? 'running'
          : meta.ok
            ? 'completed'
            : 'failed'
      output.push({
        id: message.id,
        role: 'tool',
        content: message.content,
        tool_call_id: meta.tool_call_id,
        tool_name: meta.tool_name || start?.meta?.tool_name,
        tool_args: start?.meta?.args || {},
        tool_status: persistedStatus,
        created_at: message.ts,
      })
      continue
    }
    const context = meta.active_context || []
    output.push({
      id: message.id,
      role: message.role,
      content: message.content,
      paper_ids: meta.paper_ids || context.filter((item) => item.kind === 'paper').map((item) => item.id),
      note_ids: context.filter((item) => item.kind === 'note').map((item) => item.id),
      created_at: message.ts,
    })
  }
  for (const [callId, start] of starts) {
    output.push({
      id: start.id,
      role: 'tool',
      content: '工具调用尚未返回结果。',
      tool_call_id: callId,
      tool_name: start.meta?.tool_name,
      tool_args: start.meta?.args || {},
      tool_status: 'failed',
      created_at: start.ts,
    })
  }
  return output
}

async function loadSession(meta: WorkmodeSessionMeta): Promise<BackendSession> {
  const [result, contextResult] = await Promise.all([
    rawRequest<{ messages: WorkmodeMessage[] }>(`/work/sessions/${encodeURIComponent(meta.id)}/messages?limit=60`),
    rawRequest<{ context: WorkmodeContextUsage }>(`/work/sessions/${encodeURIComponent(meta.id)}/context`),
  ])
  const lastContext = [...result.messages]
    .reverse()
    .find((message) => message.role === 'user' && message.meta?.active_context?.length)
    ?.meta?.active_context || []
  return {
    id: meta.id,
    name: meta.title,
    messages: mergeWorkmodeMessages(result.messages),
    attached_paper_ids: lastContext.filter((item) => item.kind === 'paper').map((item) => item.id),
    attached_note_ids: lastContext.filter((item) => item.kind === 'note').map((item) => item.id),
    created_at: meta.created_at,
    updated_at: meta.updated_at,
    context_percent: Math.min(100, Math.max(0, Math.round(
      ((contextResult.context.prompt_tokens_estimate || 0) / Math.max(contextResult.context.budget_tokens || 1, 1)) * 100,
    ))),
  }
}

export function mapBackendPaper(paper: BackendPaper): PaperRecord {
  const reportReady = Boolean(paper.fact_report_path)
  const placeholderReport: FactReportSection[] = reportReady
    ? [{
        id: 'backend-report',
        title: '完整客观事实报告',
        owner: 'extractor',
        entries: [{ kind: 'metadata', content: '完整报告已生成，请在正文区域阅读。' }],
      }]
    : []
  return {
    id: paper.id,
    filename: paper.original_filename,
    pdfPath: paper.paths?.pdf || null,
    archiveFilename: paper.archive_filename,
    archiveLocation: paper.archive_location,
    metadataSource: paper.metadata_source === 'manual'
      ? 'manual_review'
      : paper.metadata_source === 'layout_json'
        ? 'layout_json_fallback'
        : paper.metadata_source,
    paperType: paper.paper_type,
    verificationStatus: paper.verification_status || 'pending',
    title: paper.title || '未识别标题',
    authors: paper.authors || '等待首页元数据识别',
    firstAuthorSurname: paper.first_author_surname || '',
    year: paper.year,
    publicationDate: paper.publication_date || '',
    journal: paper.journal || '等待首页元数据识别',
    journalAbbreviation: paper.journal_abbreviation || '',
    doi: paper.doi || '',
    status: paper.status,
    processingStage: paper.stage || '',
    processingError: paper.error || '',
    tagIds: paper.tags || [],
    groupIds: paper.group_ids || [],
    siFolder: paper.paths?.si_folder || null,
    focus: paper.focus || '',
    summary: paper.summary || '',
    facts: paper.error ? [`处理错误：${paper.error}`] : [],
    factReport: placeholderReport,
    metadataTrust: paper.metadata_trust === 'pending' ? 'unknown' : paper.metadata_trust,
    metadataIssue: paper.metadata_issue || '',
  }
}

export async function checkLiteratureBackend(): Promise<boolean> {
  try {
    const project = await resolveProject()
    const health = await rawRequest<LiteratureBackendHealth>(
      `/work/projects/${encodeURIComponent(project.slug)}/literature/health`,
    )
    return isCompatibleLiteratureBackend(health)
  } catch {
    return false
  }
}

export async function listBackendPapers(): Promise<BackendPaper[]> {
  return (await literatureRequest<CatalogPaper[]>('/papers')).map(fromCatalogPaper)
}

export async function listDeletedBackendPapers(): Promise<DeletedBackendPaper[]> {
  const result = await literatureRequest<{
    papers: Array<{ trash_id: string; deleted_at: string; paper: CatalogPaper; file_count: number }>
  }>('/trash/papers')
  return result.papers.map((entry) => ({ ...entry, paper: fromCatalogPaper(entry.paper) }))
}

export async function deleteBackendPaper(paperId: string): Promise<{ trash_id: string; trash_path: string }> {
  const result = await literatureRequest<{ result: { trash_id: string; trash_path: string } }>(
    `/papers/${encodeURIComponent(paperId)}`,
    { method: 'DELETE' },
  )
  return result.result
}

export async function restoreBackendPaper(trashId: string): Promise<BackendPaper> {
  const result = await literatureRequest<{ paper: CatalogPaper }>(
    `/trash/papers/${encodeURIComponent(trashId)}/restore`,
    { method: 'POST' },
  )
  return fromCatalogPaper(result.paper)
}

export async function listBackendTags(): Promise<BackendTag[]> {
  return (await listBackendTagRegistry()).tags
}

export async function listBackendTagRegistry(): Promise<{ groups: BackendTagGroup[]; tags: BackendTag[] }> {
  return literatureRequest<{ groups: BackendTagGroup[]; tags: BackendTag[] }>('/tag-registry')
}

export async function listBackendGroups(): Promise<BackendLiteratureGroup[]> {
  return literatureRequest<BackendLiteratureGroup[]>('/groups')
}

export async function findEndNoteLibraries(): Promise<EndNoteLibraryCandidate[]> {
  return (await literatureRequest<{ libraries: EndNoteLibraryCandidate[] }>('/endnote/libraries')).libraries
}

export async function previewEndNoteLibrary(path: string): Promise<EndNotePreview> {
  return literatureRequest<EndNotePreview>('/endnote/preview', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  })
}

export async function importEndNoteLibrary(path: string): Promise<EndNoteImportResult> {
  return literatureRequest<EndNoteImportResult>('/endnote/import', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ path }),
  })
}

export async function scanBackendDuplicates(): Promise<DuplicateScanResult> {
  return literatureRequest<DuplicateScanResult>('/duplicates/scan', { method: 'POST' })
}

export async function openBackendSiFolder(paperId: string): Promise<string> {
  const result = await literatureRequest<{ path: string }>(
    `/papers/${encodeURIComponent(paperId)}/si-folder/open`,
    { method: 'POST' },
  )
  return result.path
}

export async function uploadPaper(file: File): Promise<{ paper: BackendPaper; duplicate: boolean }> {
  const result = await literatureRequest<ImportResult>(`/papers/import?filename=${encodeURIComponent(file.name)}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/pdf' },
    body: file,
  })
  return { paper: fromCatalogPaper(result.paper), duplicate: result.duplicate }
}

export async function recordImportedPapers(sessionId: string, paperIds: string[]): Promise<void> {
  const project = await resolveProject()
  await rawRequest(
    `/work/projects/${encodeURIComponent(project.slug)}/literature/sessions/${encodeURIComponent(sessionId)}/imports`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ paper_ids: paperIds }),
    },
  )
}

export async function getFactReport(paperId: string): Promise<string> {
  const project = await resolveProject()
  const response = await fetch(
    `${WORKMODE_API_ROOT}/work/projects/${encodeURIComponent(project.slug)}/literature/papers/${encodeURIComponent(paperId)}/facts`,
    { headers: authHeaders() },
  )
  if (!response.ok) throw new Error(response.status === 404 ? '客观事实报告尚未生成' : `读取报告失败：HTTP ${response.status}`)
  return response.text()
}

export function paperPdfUrl(pdfPath: string | null | undefined): string {
  if (!activeProject || !pdfPath) return ''
  return api.mediaUrl(activeProject.slug, pdfPath)
}

export async function listBackendSessions(): Promise<BackendSession[]> {
  const project = await resolveProject()
  const result = await rawRequest<{ sessions: WorkmodeSessionMeta[] }>(
    `/work/projects/${encodeURIComponent(project.slug)}/sessions?limit=60`,
  )
  return Promise.all(result.sessions.map(loadSession))
}

export async function createBackendSession(name: string): Promise<BackendSession> {
  const project = await resolveProject()
  const result = await rawRequest<{ session: WorkmodeSessionMeta }>(
    `/work/projects/${encodeURIComponent(project.slug)}/sessions`,
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: name }) },
  )
  return loadSession(result.session)
}

export async function renameBackendSession(sessionId: string, title: string): Promise<string> {
  const result = await api.updateSession(sessionId, title)
  return result.session.title
}

export async function streamLiteratureChat(
  sessionId: string,
  content: string,
  paperIds: string[],
  noteIds: string[],
  onEvent: (event: ChatStreamEvent) => void,
  signal?: AbortSignal,
): Promise<void> {
  let streamError = ''
  await streamChat(
    sessionId,
    content,
    (event) => {
      onEvent(event)
      if (event.type === 'error') streamError = String(event.message || '模型请求失败')
    },
    signal,
    [
      ...paperIds.map((id) => ({ kind: 'paper' as const, id })),
      ...noteIds.map((id) => ({ kind: 'note' as const, id })),
    ],
  )
  if (streamError) throw new Error(streamError)
}

export async function chatWithLiterature(
  sessionId: string,
  content: string,
  paperIds: string[],
  noteIds: string[],
  onEvent: (event: ChatStreamEvent) => void = () => undefined,
  signal?: AbortSignal,
): Promise<{ message: BackendChatMessage; session: BackendSession }> {
  await streamLiteratureChat(sessionId, content, paperIds, noteIds, onEvent, signal)
  const project = await resolveProject()
  const sessions = await rawRequest<{ sessions: WorkmodeSessionMeta[] }>(
    `/work/projects/${encodeURIComponent(project.slug)}/sessions?limit=200`,
  )
  const meta = sessions.sessions.find((item) => item.id === sessionId)
  if (!meta) throw new Error('session 不存在')
  const session = await loadSession(meta)
  const message = [...session.messages].reverse().find((item) => item.role === 'assistant') || {
    id: `turn-${Date.now()}`,
    role: 'assistant' as const,
    content: '',
  }
  return { message, session }
}

export async function stopBackendChat(sessionId: string): Promise<void> {
  await rawRequest(`/work/sessions/${encodeURIComponent(sessionId)}/stop`, { method: 'POST' })
}

export async function listBackendNotes(): Promise<BackendNote[]> {
  const notes = await literatureRequest<Array<Omit<BackendNote, 'source_paper_ids'>>>('/notes')
  return notes.map((note) => ({ ...note, source_paper_ids: [] }))
}

export async function saveBackendNote(
  filename: string,
  markdown: string,
  _sourcePaperIds: string[],
): Promise<BackendNote> {
  const result = await literatureRequest<{ note: Omit<BackendNote, 'source_paper_ids'> }>(
    `/notes/${encodeURIComponent(filename)}`,
    { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ markdown }) },
  )
  return { ...result.note, source_paper_ids: [] }
}

export async function deleteBackendNote(filename: string): Promise<{ trash_path: string }> {
  const result = await literatureRequest<{ result: { trash_path: string } }>(
    `/notes/${encodeURIComponent(filename)}`,
    { method: 'DELETE' },
  )
  return result.result
}

export async function getBackendMemory(): Promise<string> {
  const project = await resolveProject()
  const result = await rawRequest<{ project: string }>(`/work/projects/${encodeURIComponent(project.slug)}/memory`)
  return result.project
}

export async function saveBackendPaperReview(
  paperId: string,
  payload: { tags: Array<{ name: string; group_id: string }>; focus: string; summary: string },
): Promise<BackendPaper> {
  return fromCatalogPaper(await literatureRequest<CatalogPaper>(`/papers/${encodeURIComponent(paperId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  }))
}

export async function saveCrossLiterature(paperId: string, markdown: string): Promise<BackendPaper> {
  return fromCatalogPaper(await literatureRequest<CatalogPaper>(`/papers/${encodeURIComponent(paperId)}/cross-literature`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ markdown }),
  }))
}

export async function verifyBackendArchive(paperId: string): Promise<ArchiveVerification> {
  return literatureRequest<ArchiveVerification>(`/papers/${encodeURIComponent(paperId)}/verify`)
}

export async function archiveBackendPaper(
  paperId: string,
): Promise<{ paper: BackendPaper; verification: ArchiveVerification; index_path: string }> {
  const result = await literatureRequest<{ paper: CatalogPaper }>(`/papers/${encodeURIComponent(paperId)}/archive`, { method: 'POST' })
  return {
    paper: fromCatalogPaper(result.paper),
    verification: { ok: true, paper_id: paperId, issues: [] },
    index_path: 'processed-index.md',
  }
}

export async function compactBackendSession(sessionId: string): Promise<{
  session: BackendSession
  summary: string
  summarized_message_count: number
}> {
  const result = await rawRequest<{ compaction: { summary?: string; summarized_message_count?: number } }>(
    `/work/sessions/${encodeURIComponent(sessionId)}/compact`,
    { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ keep_recent: 6, extra_instruction: '' }) },
  )
  const project = await resolveProject()
  const sessions = await rawRequest<{ sessions: WorkmodeSessionMeta[] }>(
    `/work/projects/${encodeURIComponent(project.slug)}/sessions?limit=200`,
  )
  const meta = sessions.sessions.find((item) => item.id === sessionId)
  if (!meta) throw new Error('session 不存在')
  return {
    session: await loadSession(meta),
    summary: result.compaction.summary || '',
    summarized_message_count: result.compaction.summarized_message_count || 0,
  }
}
