import { useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { Icon } from './Icon'
import { LiteratureOnboarding } from './LiteratureOnboarding'
import { EMPTY_RUNTIME_SESSION } from './runtimeState'
import { LITERATURE_PROJECT_KEY, applicationHomeUrl, workbenchSettingsUrl } from '../literatureNavigation'
import { SKIN_RUNTIME_GUARD_KEY, skinUsesChrome, type ActiveCustomSkin } from '../customSkin'
import { MarkdownRenderer } from '../MarkdownRenderer'
import { PdfViewer } from '../PdfViewer'
import { SkinChrome } from '../SkinChrome'
import { THEMES, type ThemeId } from '../theme'
import { isNearBottom } from '../conversation'
import { projectRefreshTargets, type ProjectRefreshTarget } from '../projectChanges'
import { chooseEndNoteLibrary, openLocalPath } from '../desktop'
import {
  chatActionMessageForEvent,
  createLiveChatState,
  reduceLiveChatEvent,
  type LiteratureChatMessage as ChatMessage,
} from './chatStream'
import {
  activateBackendLiteratureProject,
  checkLiteratureBackend,
  chatWithLiterature,
  compactBackendSession,
  createBackendLiteratureProject,
  createBackendSession,
  deleteBackendPaper,
  deleteBackendNote,
  getBackendProjectInfo,
  getBackendMemory,
  getFactReport,
  findEndNoteLibraries,
  importEndNoteLibrary,
  listBackendPapers,
  listBackendGroups,
  listDeletedBackendPapers,
  listBackendSessions,
  listBackendNotes,
  listBackendLiteratureProjects,
  listBackendTagRegistry,
  mapBackendPaper,
  openBackendSiFolder,
  paperPdfUrl,
  previewEndNoteLibrary,
  recordImportedPapers,
  removeBackendProject,
  renameBackendProject,
  renameBackendSession,
  restoreBackendPaper,
  saveBackendPaperReview,
  saveBackendNote,
  saveCrossLiterature,
  scanBackendDuplicates,
  stopBackendChat,
  archiveBackendPaper,
  verifyBackendArchive,
  uploadPaper,
  type ArchiveVerification,
  type BackendNote,
  type BackendLiteratureGroup,
  type BackendSession,
  type BackendTag,
  type BackendTagGroup,
  type DeletedBackendPaper,
  type DuplicateScanResult,
  type EndNoteImportResult,
  type EndNoteLibraryCandidate,
  type EndNotePreview,
  type WorkmodeProject,
} from './literatureApi'
import {
  attachPapers,
  filterPapersByTagIds,
  resolveNoteFilename,
  statusLabel,
  updateSessionById,
  type ProjectMemoryState,
  type PaperRecord,
  type PaperStatus,
} from './model'

interface NoteDocument {
  id: string
  title: string
  filename: string
  markdown: string
  updatedAt: string
  sourcePaperIds: string[]
}

interface ConversationSession {
  id: string
  name: string
  messages: ChatMessage[]
  attachedPaperIds: string[]
  attachedNoteIds: string[]
  contextPercent: number
}

interface LiteratureAppProps {
  themeId: ThemeId
  customSkin: ActiveCustomSkin | null
}

function mapBackendSession(session: BackendSession): ConversationSession {
  return {
    id: session.id,
    name: session.name,
    messages: (session.messages || []).map((message) => ({
      id: message.id,
      role: message.role,
      text: message.content,
      paperIds: message.paper_ids,
      noteIds: message.note_ids,
      toolCallId: message.tool_call_id,
      toolName: message.tool_name,
      toolArgs: message.tool_args,
      toolStatus: message.tool_status,
    })),
    attachedPaperIds: session.attached_paper_ids || [],
    attachedNoteIds: session.attached_note_ids || [],
    contextPercent: session.context_percent,
  }
}

function mapBackendNote(note: BackendNote): NoteDocument {
  return {
    id: note.filename,
    title: note.title,
    filename: note.filename,
    markdown: note.markdown,
    updatedAt: note.updated_at ? new Date(note.updated_at).toLocaleString() : '刚刚',
    sourcePaperIds: note.source_paper_ids || [],
  }
}

function memoryRulesFromMarkdown(markdown: string): string[] {
  const bullets = markdown
    .split(/\r?\n/)
    .map((line) => line.match(/^\s*[-*]\s+(.+)/)?.[1]?.trim())
    .filter((line): line is string => Boolean(line))
  return bullets.length ? bullets : [markdown.trim()].filter(Boolean)
}

function blankNote(index: number): NoteDocument {
  const title = `新笔记 ${index}`
  return {
    id: `draft-${Date.now()}-${index}`,
    title,
    filename: `${title}.md`,
    markdown: `# ${title}\n\n> 请在这里记录经过核查的项目内容。\n`,
    updatedAt: '未保存',
    sourcePaperIds: [],
  }
}

const FACT_KIND_LABELS = {
  metadata: '基本信息',
  method: '实验条件',
  data: '数据',
  observation: '直接观察',
  author_interpretation: '作者归属',
  excerpt: '原始内容',
} as const

const METADATA_SOURCE_LABELS = {
  cite_this: 'PDF 首页 Cite This',
  layout_json_fallback: 'layout.json DOI 回退',
  manual_review: '人工确认',
  pending: '等待首页元数据',
} as const

const PAPER_TYPE_LABELS = {
  research: '研究论文 · 扁平主档',
  review: '综述 · N+1 分层主档',
  unknown: '等待文章类型判定',
} as const

const VERIFICATION_LABELS = {
  pending: '等待 verify_archive.py',
  passed: '归档校验通过',
  needs_fix: '需要修复后复验',
} as const

function messageId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function StatusDot({ status }: { status: PaperStatus }) {
  return <span className={`status-dot status-${status}`} aria-hidden="true" />
}

export default function LiteratureApp({ themeId, customSkin }: LiteratureAppProps) {
  const emptySession = EMPTY_RUNTIME_SESSION as ConversationSession
  const [papers, setPapers] = useState<PaperRecord[]>([])
  const [notes, setNotes] = useState<NoteDocument[]>([])
  const [sessions, setSessions] = useState<ConversationSession[]>([emptySession])
  const [activeSessionId, setActiveSessionId] = useState(emptySession.id)
  const [detailPaperId, setDetailPaperId] = useState<string | null>(null)
  const [detailTab, setDetailTab] = useState<'overview' | 'facts' | 'pdf'>('overview')
  const [pdfUrls, setPdfUrls] = useState<Record<string, string>>({})
  const [factReportMarkdowns, setFactReportMarkdowns] = useState<Record<string, string>>({})
  const [backendMode, setBackendMode] = useState<'connecting' | 'connected' | 'unavailable'>('connecting')
  const [backendError, setBackendError] = useState('')
  const [projectInfo, setProjectInfo] = useState<WorkmodeProject | null>(null)
  const [projectOptions, setProjectOptions] = useState<WorkmodeProject[]>([])
  const [projectManagerOpen, setProjectManagerOpen] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [editingProjectSlug, setEditingProjectSlug] = useState<string | null>(null)
  const [editingProjectName, setEditingProjectName] = useState('')
  const [projectActionBusy, setProjectActionBusy] = useState(false)
  const [projectManagerError, setProjectManagerError] = useState('')
  const [trashOpen, setTrashOpen] = useState(false)
  const [deletedPapers, setDeletedPapers] = useState<DeletedBackendPaper[]>([])
  const [trashBusyId, setTrashBusyId] = useState('')
  const [trashError, setTrashError] = useState('')
  const [tagRegistry, setTagRegistry] = useState<BackendTag[]>([])
  const [tagGroups, setTagGroups] = useState<BackendTagGroup[]>([])
  const [literatureGroups, setLiteratureGroups] = useState<BackendLiteratureGroup[]>([])
  const [search, setSearch] = useState('')
  const [selectedTagIds, setSelectedTagIds] = useState<string[]>([])
  const [selectedGroupId, setSelectedGroupId] = useState('')
  const [tagFilterOpen, setTagFilterOpen] = useState(false)
  const [tagQuery, setTagQuery] = useState('')
  const hudLayoutActive = Boolean(customSkin?.enabled && skinUsesChrome(customSkin.skin))
    || THEMES.some((theme) => theme.id === themeId && theme.layout === 'hud')
  const [input, setInput] = useState('')
  const [dragActive, setDragActive] = useState(false)
  const [pendingImportFiles, setPendingImportFiles] = useState<File[]>([])
  const [importingPapers, setImportingPapers] = useState(false)
  const [endNoteOpen, setEndNoteOpen] = useState(false)
  const [endNoteCandidates, setEndNoteCandidates] = useState<EndNoteLibraryCandidate[]>([])
  const [endNotePath, setEndNotePath] = useState('')
  const [endNotePreview, setEndNotePreview] = useState<EndNotePreview | null>(null)
  const [endNoteResult, setEndNoteResult] = useState<EndNoteImportResult | null>(null)
  const [duplicateResult, setDuplicateResult] = useState<DuplicateScanResult | null>(null)
  const [endNoteBusy, setEndNoteBusy] = useState(false)
  const [endNoteError, setEndNoteError] = useState('')
  const [renameSessionOpen, setRenameSessionOpen] = useState(false)
  const [renameSessionTitle, setRenameSessionTitle] = useState('')
  const [renamingSession, setRenamingSession] = useState(false)
  const [memoryOpen, setMemoryOpen] = useState(false)
  const [notesOpen, setNotesOpen] = useState(false)
  const [activeNoteId, setActiveNoteId] = useState('')
  const [noteMode, setNoteMode] = useState<'edit' | 'preview'>('preview')
  const [memoryState, setMemoryState] = useState<ProjectMemoryState>({
    projectMemory: [],
  })
  const [reviewFocusDraft, setReviewFocusDraft] = useState('')
  const [reviewSummaryDraft, setReviewSummaryDraft] = useState('')
  const [reviewTagsDraft, setReviewTagsDraft] = useState('')
  const [crossLiteratureDraft, setCrossLiteratureDraft] = useState('')
  const [archiveVerification, setArchiveVerification] = useState<ArchiveVerification | null>(null)
  const [actionMessage, setActionMessage] = useState('')
  const [streaming, setStreaming] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const notePreviewRef = useRef<HTMLDivElement>(null)
  const messageStreamRef = useRef<HTMLDivElement>(null)
  const followingLatestRef = useRef(true)
  const refreshTargetsRef = useRef<Set<ProjectRefreshTarget>>(new Set())
  const refreshTimerRef = useRef<number | null>(null)
  const [showBackToLatest, setShowBackToLatest] = useState(false)
  const dragDepthRef = useRef(0)
  const streamAbortRef = useRef<AbortController | null>(null)
  const stopRequestedRef = useRef(false)

  const activeSession = sessions.find((session) => session.id === activeSessionId) ?? sessions[0]

  function scrollToLatest(behavior: ScrollBehavior = 'auto') {
    const viewport = messageStreamRef.current
    if (!viewport) return
    followingLatestRef.current = true
    setShowBackToLatest(false)
    viewport.scrollTo({ top: viewport.scrollHeight, behavior })
  }

  function handleMessageStreamScroll() {
    const viewport = messageStreamRef.current
    if (!viewport) return
    const nearBottom = isNearBottom(viewport)
    followingLatestRef.current = nearBottom
    setShowBackToLatest(!nearBottom)
  }

  async function refreshProjection(targets: Set<ProjectRefreshTarget>) {
    const jobs: Promise<void>[] = []
    if (targets.has('papers')) {
      jobs.push(listBackendPapers().then((records) => {
        const mapped = records.map(mapBackendPaper)
        const availablePaperIds = new Set(mapped.map((paper) => paper.id))
        setPapers(mapped)
        setPdfUrls(Object.fromEntries(mapped.map((paper) => [paper.id, paperPdfUrl(paper.pdfPath)])))
        setSessions((current) => current.map((session) => ({
          ...session,
          attachedPaperIds: session.attachedPaperIds.filter((id) => availablePaperIds.has(id)),
        })))
        setDetailPaperId((current) => current && availablePaperIds.has(current) ? current : null)
      }))
    }
    if (targets.has('tags')) {
      jobs.push(listBackendTagRegistry().then((registry) => {
        setTagRegistry(registry.tags)
        setTagGroups(registry.groups)
      }))
    }
    if (targets.has('groups')) {
      jobs.push(listBackendGroups().then(setLiteratureGroups))
    }
    if (targets.has('notes')) {
      jobs.push(listBackendNotes().then((storedNotes) => {
        const mapped = storedNotes.map(mapBackendNote)
        setNotes(mapped)
        setActiveNoteId((current) => (
          mapped.some((note) => note.id === current) ? current : mapped[0]?.id || ''
        ))
      }))
    }
    await Promise.all(jobs)
  }

  function scheduleProjectionRefresh(changedPaths: string[]) {
    const targets = projectRefreshTargets(changedPaths)
    for (const target of targets) refreshTargetsRef.current.add(target)
    if (refreshTimerRef.current !== null) window.clearTimeout(refreshTimerRef.current)
    refreshTimerRef.current = window.setTimeout(() => {
      const pending = new Set(refreshTargetsRef.current)
      refreshTargetsRef.current.clear()
      refreshTimerRef.current = null
      void refreshProjection(pending).catch((error) => {
        setActionMessage(`项目内容刷新失败：${error instanceof Error ? error.message : '未知错误'}`)
      })
    }, 120)
  }

  function reconcileProjection() {
    return refreshProjection(new Set<ProjectRefreshTarget>(['papers', 'tags', 'groups', 'notes']))
  }

  useEffect(() => {
    followingLatestRef.current = true
    setShowBackToLatest(false)
  }, [activeSessionId])

  useEffect(() => {
    if (!followingLatestRef.current) return
    const frame = window.requestAnimationFrame(() => scrollToLatest())
    return () => window.cancelAnimationFrame(frame)
  }, [activeSession.messages])

  useEffect(() => () => {
    if (refreshTimerRef.current !== null) window.clearTimeout(refreshTimerRef.current)
  }, [])

  useEffect(() => {
    let active = true
    async function connectBackend() {
      const projects = await listBackendLiteratureProjects()
      if (!active) return
      setProjectOptions(projects)
      if (!projects.length) {
        setProjectInfo(null)
        setBackendError('还没有文献项目。请新建一个项目后开始使用。')
        setBackendMode('unavailable')
        setProjectManagerOpen(true)
        return
      }
      const connected = await checkLiteratureBackend()
      if (!active) return
      if (!connected) {
        throw new Error('无法连接正式 Workmode 文献项目')
      }
      const [project, records, storedSessions, storedTagRegistry, storedGroups, storedNotes, storedMemory] = await Promise.all([
        getBackendProjectInfo(),
        listBackendPapers(),
        listBackendSessions(),
        listBackendTagRegistry(),
        listBackendGroups(),
        listBackendNotes(),
        getBackendMemory(),
      ])
      if (!active) return
      const mapped = records.map(mapBackendPaper)
      const availableSessions = storedSessions.length
        ? storedSessions
        : [await createBackendSession('文献讨论 1')]
      if (!active) return
      setPapers(mapped)
      setProjectInfo(project)
      setTagRegistry(storedTagRegistry.tags)
      setTagGroups(storedTagRegistry.groups)
      setLiteratureGroups(storedGroups)
      const mappedNotes = storedNotes.map(mapBackendNote)
      const nextNotes = mappedNotes.length ? mappedNotes : [blankNote(1)]
      setNotes(nextNotes)
      setActiveNoteId(nextNotes[0].id)
      setMemoryState({
        projectMemory: memoryRulesFromMarkdown(storedMemory),
      })
      const availablePaperIds = new Set(mapped.map((paper) => paper.id))
      setSessions(availableSessions.map(mapBackendSession).map((session) => ({
        ...session,
        attachedPaperIds: session.attachedPaperIds.filter((id) => availablePaperIds.has(id)),
      })))
      setActiveSessionId(availableSessions[0].id)
      setPdfUrls(Object.fromEntries(mapped.map((paper) => [paper.id, paperPdfUrl(paper.pdfPath)])))
      setBackendError('')
      setBackendMode('connected')
    }
    void connectBackend().catch((error) => {
      if (!active) return
      const message = error instanceof Error ? error.message : '未知连接错误'
      setPapers([])
      setProjectInfo(null)
      setNotes([])
      setTagRegistry([])
      setTagGroups([])
      setLiteratureGroups([])
      setMemoryState({ projectMemory: [] })
      setSessions([emptySession])
      setActiveSessionId(emptySession.id)
      setBackendError(message)
      setBackendMode('unavailable')
    })
    return () => {
      active = false
    }
  }, [])

  const filteredPapers = useMemo(() => {
    const query = search.trim().toLocaleLowerCase()
    const matchesSearch = papers.filter((paper) => {
      const matchesText =
        !query ||
        [
          paper.title,
          paper.authors,
          paper.firstAuthorSurname,
          paper.journal,
          paper.journalAbbreviation,
          paper.doi,
          paper.publicationDate,
          paper.filename,
          ...paper.groupIds.map((id) => literatureGroups.find((group) => group.id === id)?.name || id),
        ]
          .join(' ')
          .toLocaleLowerCase()
          .includes(query)
      return matchesText
    })
    const matchesGroup = selectedGroupId
      ? matchesSearch.filter((paper) => paper.groupIds.includes(selectedGroupId))
      : matchesSearch
    return filterPapersByTagIds(matchesGroup, selectedTagIds)
  }, [papers, search, selectedTagIds, selectedGroupId, literatureGroups])

  const tagSearchResults = useMemo(() => {
    const query = tagQuery.trim().toLocaleLowerCase()
    if (!query) return []
    return tagRegistry.filter((tag) =>
      [tag.name, ...tag.aliases].some((label) => label.toLocaleLowerCase().includes(query)),
    )
  }, [tagQuery, tagRegistry])

  const detailPaper = papers.find((paper) => paper.id === detailPaperId) ?? null

  useEffect(() => {
    if (!detailPaper) return
    setReviewFocusDraft(detailPaper.focus || '')
    setReviewSummaryDraft(detailPaper.summary || '')
    setReviewTagsDraft(
      detailPaper.tagIds
        .map((tagId) => tagRegistry.find((tag) => tag.id === tagId)?.name || tagId)
        .join('，'),
    )
    setCrossLiteratureDraft('')
    setArchiveVerification(null)
    setActionMessage('')
  }, [detailPaperId, detailPaper?.focus, detailPaper?.summary, detailPaper?.tagIds, tagRegistry])

  useEffect(() => {
    if (detailTab !== 'facts' || !detailPaper?.factReport.length || factReportMarkdowns[detailPaper.id]) return
    let active = true
    void getFactReport(detailPaper.id)
      .then((markdown) => {
        if (active) setFactReportMarkdowns((current) => ({ ...current, [detailPaper.id]: markdown }))
      })
      .catch(() => undefined)
    return () => {
      active = false
    }
  }, [detailPaper, detailTab, factReportMarkdowns])
  const attachedPapers = activeSession.attachedPaperIds
    .map((id) => papers.find((paper) => paper.id === id))
    .filter((paper): paper is PaperRecord => Boolean(paper))
  const attachedNotes = activeSession.attachedNoteIds
    .map((id) => notes.find((note) => note.id === id))
    .filter((note): note is NoteDocument => Boolean(note))
  const activeNote = notes.find((note) => note.id === activeNoteId) ?? notes[0]
  const noteMaintenanceRules = memoryState.projectMemory.filter((memory) =>
    /笔记|引用|事实|命名/.test(memory),
  )

  function updateActiveSession(updater: (session: ConversationSession) => ConversationSession) {
    setSessions((current) => updateSessionById(current, activeSessionId, updater))
  }

  function setActiveMessages(updater: (messages: ChatMessage[]) => ChatMessage[]) {
    updateActiveSession((session) => ({ ...session, messages: updater(session.messages) }))
  }

  function setActiveAttachments(updater: (paperIds: string[]) => string[]) {
    const nextPaperIds = updater(activeSession.attachedPaperIds)
    updateActiveSession((session) => ({ ...session, attachedPaperIds: nextPaperIds }))
  }

  function setActiveNoteAttachments(updater: (noteIds: string[]) => string[]) {
    const nextNoteIds = updater(activeSession.attachedNoteIds)
    updateActiveSession((session) => ({ ...session, attachedNoteIds: nextNoteIds }))
  }

  async function openProjectManager() {
    setProjectManagerError('')
    setProjectManagerOpen(true)
    try {
      setProjectOptions(await listBackendLiteratureProjects())
    } catch (error) {
      setProjectManagerError(`项目列表读取失败：${error instanceof Error ? error.message : '未知错误'}`)
    }
  }

  async function openPaperTrash() {
    if (backendMode !== 'connected') return
    setTrashOpen(true)
    setTrashError('')
    try {
      setDeletedPapers(await listDeletedBackendPapers())
    } catch (error) {
      setTrashError(`回收站读取失败：${error instanceof Error ? error.message : '未知错误'}`)
    }
  }

  async function createManagedProject(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = newProjectName.trim()
    if (!name || projectActionBusy) return
    setProjectActionBusy(true)
    setProjectManagerError('')
    try {
      await createBackendLiteratureProject(name)
      window.location.reload()
    } catch (error) {
      setProjectManagerError(`项目创建失败：${error instanceof Error ? error.message : '未知错误'}`)
      setProjectActionBusy(false)
    }
  }

  async function switchLiteratureProject(slug: string) {
    if (projectActionBusy || slug === projectInfo?.slug) {
      if (slug === projectInfo?.slug) setProjectManagerOpen(false)
      return
    }
    setProjectActionBusy(true)
    setProjectManagerError('')
    try {
      await activateBackendLiteratureProject(slug)
      window.location.reload()
    } catch (error) {
      setProjectManagerError(`项目切换失败：${error instanceof Error ? error.message : '未知错误'}`)
      setProjectActionBusy(false)
    }
  }

  function startProjectRename(project: WorkmodeProject) {
    setEditingProjectSlug(project.slug)
    setEditingProjectName(project.name)
    setProjectManagerError('')
  }

  async function commitProjectRename(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const name = editingProjectName.trim()
    if (!editingProjectSlug || !name || projectActionBusy) return
    setProjectActionBusy(true)
    setProjectManagerError('')
    try {
      const updated = await renameBackendProject(editingProjectSlug, name)
      setProjectOptions((current) => current.map((project) => project.slug === updated.slug ? updated : project))
      if (projectInfo?.slug === updated.slug) setProjectInfo(updated)
      setEditingProjectSlug(null)
      setEditingProjectName('')
      setActionMessage('文献项目名称已修改。')
    } catch (error) {
      setProjectManagerError(`项目重命名失败：${error instanceof Error ? error.message : '未知错误'}`)
    } finally {
      setProjectActionBusy(false)
    }
  }

  async function removeLiteratureProject(project: WorkmodeProject) {
    if (projectActionBusy || streaming) return
    const confirmed = window.confirm(
      `从 Workmode 中移除文献项目“${project.name}”？\n\n项目文件不会删除：\n${project.root_path}\n\n如需删除实体文件夹，请稍后在文件管理器中手动处理。`,
    )
    if (!confirmed) return
    setProjectActionBusy(true)
    setProjectManagerError('')
    try {
      await removeBackendProject(project.slug)
      const remaining = projectOptions.filter((item) => item.slug !== project.slug)
      if (remaining.length) {
        await activateBackendLiteratureProject(remaining[0].slug)
      } else {
        window.sessionStorage.removeItem(LITERATURE_PROJECT_KEY)
      }
      window.location.reload()
    } catch (error) {
      setProjectManagerError(`项目移除失败：${error instanceof Error ? error.message : '未知错误'}`)
      setProjectActionBusy(false)
    }
  }

  function createSession() {
    if (backendMode !== 'connected') {
      setActionMessage('后端未连接，不能创建 session。')
      return
    }
    void createBackendSession(`新对话 ${sessions.length + 1}`).then((stored) => {
      const session = mapBackendSession(stored)
      setSessions((current) => [...current, session])
      setActiveSessionId(session.id)
    }).catch((error) => {
      setActiveMessages((current) => [...current, {
        id: messageId('session-error'),
        role: 'assistant',
        text: `创建持久会话失败：${error instanceof Error ? error.message : '未知错误'}`,
      }])
    })
  }

  function openSessionRename() {
    setRenameSessionTitle(activeSession.name)
    setRenameSessionOpen(true)
  }

  async function renameActiveSession(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const title = renameSessionTitle.trim()
    if (!title || renamingSession) return
    setRenamingSession(true)
    try {
      const savedTitle = await renameBackendSession(activeSession.id, title)
      setSessions((current) => updateSessionById(current, activeSession.id, (session) => ({
        ...session,
        name: savedTitle,
      })))
      setRenameSessionOpen(false)
      setActionMessage('会话名称已修改')
    } catch (error) {
      setActionMessage(`会话重命名失败：${error instanceof Error ? error.message : '未知错误'}`)
    } finally {
      setRenamingSession(false)
    }
  }

  function updatePaper(id: string, updater: (paper: PaperRecord) => PaperRecord) {
    setPapers((current) => current.map((paper) => (paper.id === id ? updater(paper) : paper)))
  }

  function togglePaperAttachment(id: string) {
    setActiveAttachments((current) =>
      current.includes(id) ? current.filter((paperId) => paperId !== id) : attachPapers(current, [id]),
    )
  }

  function toggleNoteAttachment(id: string) {
    setActiveNoteAttachments((current) =>
      current.includes(id) ? current.filter((noteId) => noteId !== id) : [...current, id],
    )
  }

  function createBlankNote() {
    if (backendMode !== 'connected') {
      setActionMessage('后端未连接，不能创建笔记。')
      return
    }
    const note = blankNote(notes.length + 1)
    note.filename = resolveNoteFilename(note.title, notes.map((item) => item.filename))
    setNotes((current) => [...current, note])
    setActiveNoteId(note.id)
    setNoteMode('edit')
  }

  function updateActiveNote(markdown: string) {
    if (!activeNote) return
    setNotes((current) => current.map((note) =>
      note.id === activeNote.id ? { ...note, markdown, updatedAt: '刚刚' } : note,
    ))
  }

  async function saveActiveNote() {
    if (!activeNote) return
    if (backendMode !== 'connected') {
      setActionMessage('后端未连接，笔记没有保存。')
      return
    }
    try {
      const stored = await saveBackendNote(
        activeNote.filename,
        activeNote.markdown,
        activeNote.sourcePaperIds.length
          ? activeNote.sourcePaperIds
          : activeSession.attachedPaperIds,
      )
      const mapped = mapBackendNote(stored)
      setNotes((current) => current.map((note) => note.id === activeNote.id ? mapped : note))
      setActiveNoteId(mapped.id)
      if (activeSession.attachedNoteIds.includes(activeNote.id)) {
        const nextNoteIds = activeSession.attachedNoteIds.map((id) => id === activeNote.id ? mapped.id : id)
        updateActiveSession((session) => ({ ...session, attachedNoteIds: nextNoteIds }))
      }
      setActionMessage(`已写入 ${mapped.filename}`)
    } catch (error) {
      setActionMessage(`笔记保存失败：${error instanceof Error ? error.message : '未知错误'}`)
    }
  }

  async function deleteActiveNote() {
    if (!activeNote || backendMode !== 'connected') return
    const isDraft = activeNote.id.startsWith('draft-')
    if (!isDraft && !window.confirm(`删除笔记“${activeNote.title}”？\n\n笔记会移入项目 notes/.trash，可从项目文件夹中恢复。`)) {
      return
    }
    try {
      let trashPath = ''
      if (!isDraft) {
        const result = await deleteBackendNote(activeNote.filename)
        trashPath = result.trash_path
      }
      const remaining = notes.filter((note) => note.id !== activeNote.id)
      const nextNotes = remaining.length ? remaining : [blankNote(1)]
      setNotes(nextNotes)
      setActiveNoteId(nextNotes[0].id)
      setSessions((current) => current.map((session) => ({
        ...session,
        attachedNoteIds: session.attachedNoteIds.filter((id) => id !== activeNote.id),
      })))
      setActionMessage(isDraft ? '未保存的笔记草稿已移除。' : `笔记已移入回收目录：${trashPath}`)
    } catch (error) {
      setActionMessage(`笔记删除失败：${error instanceof Error ? error.message : '未知错误'}`)
    }
  }

  async function confirmPaperReview() {
    if (!detailPaper || backendMode !== 'connected') return
    const names = reviewTagsDraft
      .split(/[，,;；\n]+/)
      .map((name) => name.trim())
      .filter(Boolean)
    try {
      const stored = await saveBackendPaperReview(detailPaper.id, {
        tags: names.map((name) => ({
          name,
          group_id: tagRegistry.find((tag) =>
            tag.name.toLocaleLowerCase() === name.toLocaleLowerCase()
            || tag.aliases.some((alias) => alias.toLocaleLowerCase() === name.toLocaleLowerCase()),
          )?.group_id || tagGroups[0]?.id || 'ungrouped',
        })),
        focus: reviewFocusDraft,
        summary: reviewSummaryDraft,
      })
      updatePaper(detailPaper.id, () => mapBackendPaper(stored))
      const registry = await listBackendTagRegistry()
      setTagRegistry(registry.tags)
      setTagGroups(registry.groups)
      setActionMessage('标签、关注点和摘要已写回文献记录。')
    } catch (error) {
      setActionMessage(`记录写入失败：${error instanceof Error ? error.message : '未知错误'}`)
    }
  }

  async function confirmCrossLiterature() {
    if (!detailPaper || backendMode !== 'connected') return
    try {
      const stored = await saveCrossLiterature(detailPaper.id, crossLiteratureDraft)
      updatePaper(detailPaper.id, () => mapBackendPaper(stored))
      const markdown = await getFactReport(detailPaper.id)
      setFactReportMarkdowns((current) => ({ ...current, [detailPaper.id]: markdown }))
      setActionMessage('跨文献关系已写入事实报告第 6 段。')
    } catch (error) {
      setActionMessage(`跨文献段写入失败：${error instanceof Error ? error.message : '未知错误'}`)
    }
  }

  async function verifyAndArchivePaper() {
    if (!detailPaper || backendMode !== 'connected') return
    try {
      const verification = await verifyBackendArchive(detailPaper.id)
      setArchiveVerification(verification)
      if (!verification.ok) {
        setActionMessage(`归档校验未通过：${verification.issues.join('；')}`)
        return
      }
      const result = await archiveBackendPaper(detailPaper.id)
      updatePaper(detailPaper.id, () => mapBackendPaper(result.paper))
      setArchiveVerification(result.verification)
      setPdfUrls((current) => ({ ...current, [detailPaper.id]: paperPdfUrl(result.paper.paths?.pdf) }))
      setActionMessage('归档完成：PDF、MinerU 产物、事实报告与处理结果索引已同步。')
    } catch (error) {
      setActionMessage(`归档失败：${error instanceof Error ? error.message : '未知错误'}`)
    }
  }

  async function deleteDetailPaper() {
    if (!detailPaper || backendMode !== 'connected' || streaming) return
    const paper = detailPaper
    if (!window.confirm(`将文献“${paper.title}”移入回收站？\n\nPDF、解析产物和目录记录会一起移入项目回收站；历史对话不会被改写。`)) return
    setTrashBusyId(paper.id)
    try {
      await deleteBackendPaper(paper.id)
      setPapers((current) => current.filter((item) => item.id !== paper.id))
      setSessions((current) => current.map((session) => ({
        ...session,
        attachedPaperIds: session.attachedPaperIds.filter((id) => id !== paper.id),
      })))
      setPdfUrls((current) => {
        const next = { ...current }
        delete next[paper.id]
        return next
      })
      setFactReportMarkdowns((current) => {
        const next = { ...current }
        delete next[paper.id]
        return next
      })
      setDetailPaperId(null)
      setActionMessage('文献已移入回收站，可从文献库顶部的回收站恢复。')
    } catch (error) {
      setActionMessage(`文献删除失败：${error instanceof Error ? error.message : '未知错误'}`)
    } finally {
      setTrashBusyId('')
    }
  }

  async function restoreDeletedPaper(entry: DeletedBackendPaper) {
    if (trashBusyId) return
    setTrashBusyId(entry.trash_id)
    setTrashError('')
    try {
      const restored = await restoreBackendPaper(entry.trash_id)
      const mapped = mapBackendPaper(restored)
      setPapers((current) => current.some((paper) => paper.id === mapped.id) ? current : [...current, mapped])
      setPdfUrls((current) => ({ ...current, [mapped.id]: paperPdfUrl(mapped.pdfPath) }))
      setDeletedPapers((current) => current.filter((item) => item.trash_id !== entry.trash_id))
      setActionMessage(`已恢复文献：${mapped.title}`)
    } catch (error) {
      setTrashError(`文献恢复失败：${error instanceof Error ? error.message : '未知错误'}`)
    } finally {
      setTrashBusyId('')
    }
  }

  function downloadActiveNoteMarkdown() {
    if (!activeNote) return
    const blob = new Blob([activeNote.markdown], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = activeNote.filename
    anchor.click()
    URL.revokeObjectURL(url)
  }

  function exportActiveNotePdf() {
    if (!activeNote) return
    const rendered = notePreviewRef.current?.innerHTML
    if (!rendered) return
    const printWindow = window.open('', '_blank', 'width=960,height=800')
    if (!printWindow) return
    const safeTitle = activeNote.title.replace(/[<>&]/g, '')
    printWindow.document.write(`<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>${safeTitle}</title><style>body{font:15px/1.75 "Microsoft YaHei",sans-serif;color:#17202a;max-width:820px;margin:40px auto;padding:0 28px}h1,h2,h3{line-height:1.35;margin-top:1.6em}blockquote{margin:1em 0;padding:.7em 1em;border-left:4px solid #5b8def;background:#f3f6fa;color:#425466}table{width:100%;border-collapse:collapse;margin:1em 0}th,td{border:1px solid #cfd7df;padding:7px 9px;text-align:left}code{font-family:Consolas,monospace;background:#eef2f6;padding:.1em .3em;border-radius:3px}@page{size:A4;margin:16mm}@media print{body{margin:0;max-width:none;padding:0}}</style></head><body>${rendered}</body></html>`)
    printWindow.document.close()
    printWindow.focus()
    window.setTimeout(() => printWindow.print(), 250)
  }

  function openPaperDetail(id: string, tab: 'overview' | 'facts' | 'pdf' = 'overview') {
    setDetailPaperId(id)
    setDetailTab(tab)
  }

  function toggleTagFilter(id: string) {
    setSelectedTagIds((current) =>
      current.includes(id) ? current.filter((tagId) => tagId !== id) : [...current, id],
    )
  }

  function handleFiles(fileList: FileList | File[]) {
    const pdfFiles = Array.from(fileList).filter(
      (file) => file.type === 'application/pdf' || file.name.toLocaleLowerCase().endsWith('.pdf'),
    )

    if (!pdfFiles.length) {
      setActionMessage('文献模式目前只接收 PDF。其他格式没有进入项目。')
      return
    }
    if (backendMode !== 'connected') {
      setActionMessage('后端未连接，PDF 没有上传。')
      return
    }
    setActionMessage('')
    setPendingImportFiles(pdfFiles)
  }

  function openEndNoteImport() {
    setEndNoteCandidates([])
    setEndNotePath('')
    setEndNotePreview(null)
    setEndNoteResult(null)
    setDuplicateResult(null)
    setEndNoteError('')
    setEndNoteOpen(true)
  }

  async function loadEndNotePreview(path: string) {
    setEndNoteBusy(true)
    setEndNoteError('')
    try {
      const preview = await previewEndNoteLibrary(path)
      setEndNotePath(path)
      setEndNotePreview(preview)
    } catch (error) {
      setEndNoteError(`无法读取这个 EndNote 文献库：${error instanceof Error ? error.message : '未知错误'}`)
    } finally {
      setEndNoteBusy(false)
    }
  }

  async function autoFindEndNote() {
    setEndNoteBusy(true)
    setEndNoteError('')
    try {
      const candidates = await findEndNoteLibraries()
      setEndNoteCandidates(candidates)
      if (!candidates.length) {
        setEndNoteError('没有自动找到 EndNote 文献库。可以改用“手动选择”。')
      } else if (candidates.length === 1) {
        await loadEndNotePreview(candidates[0].path)
      }
    } catch (error) {
      setEndNoteError(`自动查找失败：${error instanceof Error ? error.message : '未知错误'}`)
    } finally {
      setEndNoteBusy(false)
    }
  }

  async function manuallyChooseEndNote() {
    try {
      const path = await chooseEndNoteLibrary()
      if (!path) {
        setEndNoteError('当前浏览器不能直接选择本机 EndNote 文献库；请使用 Workmode 桌面版。')
        return
      }
      await loadEndNotePreview(path)
    } catch (error) {
      setEndNoteError(`选择文件失败：${error instanceof Error ? error.message : '未知错误'}`)
    }
  }

  async function confirmEndNoteImport() {
    if (!endNotePath || !endNotePreview || endNoteBusy) return
    setEndNoteBusy(true)
    setEndNoteError('')
    try {
      const result = await importEndNoteLibrary(endNotePath)
      setEndNoteResult(result)
      await reconcileProjection()
      setActionMessage(`EndNote 导入完成：成功 ${result.imported_count} 篇，失败 ${result.failed_count} 篇。`)
    } catch (error) {
      setEndNoteError(`导入失败：${error instanceof Error ? error.message : '未知错误'}`)
    } finally {
      setEndNoteBusy(false)
    }
  }

  async function scanDuplicatesAfterImport() {
    setEndNoteBusy(true)
    setEndNoteError('')
    try {
      setDuplicateResult(await scanBackendDuplicates())
    } catch (error) {
      setEndNoteError(`查重失败：${error instanceof Error ? error.message : '未知错误'}`)
    } finally {
      setEndNoteBusy(false)
    }
  }

  async function openPaperSiFolder(paperId: string) {
    try {
      const path = await openBackendSiFolder(paperId)
      const opened = await openLocalPath(path)
      setActionMessage(opened ? '已打开 SI 文件夹。' : `SI 文件夹：${path}`)
    } catch (error) {
      setActionMessage(`无法打开 SI 文件夹：${error instanceof Error ? error.message : '未知错误'}`)
    }
  }

  async function confirmPendingImport() {
    if (!pendingImportFiles.length || importingPapers || backendMode !== 'connected') return
    const files = pendingImportFiles
    setImportingPapers(true)
    setActionMessage(`正在入库 ${files.length} 篇 PDF…`)
    const importedIds: string[] = []
    const failures: string[] = []
    let duplicateCount = 0
    for (const file of files) {
      try {
        const result = await uploadPaper(file)
        const mapped = mapBackendPaper(result.paper)
        importedIds.push(mapped.id)
        if (result.duplicate) duplicateCount += 1
        setPapers((current) => [mapped, ...current.filter((paper) => paper.id !== mapped.id)])
        setPdfUrls((current) => ({ ...current, [mapped.id]: paperPdfUrl(mapped.pdfPath) }))
      } catch (error) {
        failures.push(`${file.name}：${error instanceof Error ? error.message : '未知错误'}`)
      }
    }
    const uniqueImportedIds = [...new Set(importedIds)]
    let contextRecorded = false
    if (uniqueImportedIds.length) {
      try {
        await recordImportedPapers(activeSessionId, uniqueImportedIds)
        contextRecorded = true
      } catch (error) {
        failures.push(`系统上下文：${error instanceof Error ? error.message : '写入失败'}`)
      }
    }
    setPendingImportFiles([])
    setImportingPapers(false)
    const importedCount = uniqueImportedIds.length
    const duplicateText = duplicateCount ? `，其中 ${duplicateCount} 篇为已有文献` : ''
    const contextText = importedCount && !contextRecorded ? '；文献已入库，但系统上下文记录失败' : ''
    const failureText = failures.length ? `；${failures.length} 项失败：${failures.join('；')}` : ''
    setActionMessage(`已确认入库 ${importedCount} 篇${duplicateText}${contextText}${failureText}`)
  }

  function sendMessage() {
    const text = input.trim()
    if (!text || streaming) return
    if (backendMode !== 'connected') {
      setActionMessage(`真实后端未连接：${backendError || '请检查 8765 服务'}`)
      return
    }
    const activeSessionSnapshot = activeSession
    const activeSessionIdSnapshot = activeSessionId
    const controller = new AbortController()
    streamAbortRef.current = controller
    stopRequestedRef.current = false
    followingLatestRef.current = true
    setShowBackToLatest(false)
    setInput('')
    setStreaming(true)
    setActionMessage('')
    const userMessage: ChatMessage = {
      id: messageId('user'),
      role: 'user',
      text,
      paperIds: activeSessionSnapshot.attachedPaperIds.length ? activeSessionSnapshot.attachedPaperIds : undefined,
      noteIds: activeSessionSnapshot.attachedNoteIds.length ? activeSessionSnapshot.attachedNoteIds : undefined,
    }
    let liveState = createLiveChatState(
      [...activeSessionSnapshot.messages, userMessage],
      messageId('run'),
      activeSessionSnapshot.contextPercent,
    )
    setSessions((current) => current.map((session) => session.id === activeSessionIdSnapshot
      ? { ...session, messages: liveState.messages }
      : session))

    void chatWithLiterature(
      activeSessionIdSnapshot,
      text,
      activeSessionSnapshot.attachedPaperIds,
      activeSessionSnapshot.attachedNoteIds,
      (event) => {
        liveState = reduceLiveChatEvent(liveState, event)
        setSessions((current) => current.map((session) => session.id === activeSessionIdSnapshot
          ? {
              ...session,
              messages: liveState.messages,
              contextPercent: liveState.contextPercent,
            }
          : session))
        setActionMessage((current) => chatActionMessageForEvent(current, event))
        if (event.type === 'tool_result') {
          const changedPaths = Array.isArray(event.changed_paths) ? event.changed_paths : []
          if (changedPaths.length) scheduleProjectionRefresh(changedPaths)
        }
      },
      controller.signal,
    ).then((result) => {
      setActionMessage('')
      const stored = mapBackendSession(result.session)
      setSessions((current) => current.map((session) => session.id === stored.id ? {
        ...stored,
        attachedPaperIds: session.attachedPaperIds,
        attachedNoteIds: session.attachedNoteIds,
      } : session))
      void reconcileProjection().catch((error) => {
        setActionMessage(`对话已完成，但项目内容刷新失败：${error instanceof Error ? error.message : '未知错误'}`)
      })
    }).catch((error) => {
      if (stopRequestedRef.current || controller.signal.aborted) {
        setActionMessage('本轮生成已停止。')
        void listBackendSessions().then((storedSessions) => {
          const stored = storedSessions.find((session) => session.id === activeSessionIdSnapshot)
          if (!stored) return
          const mapped = mapBackendSession(stored)
          setSessions((current) => current.map((session) => session.id === mapped.id
            ? {
                ...mapped,
                attachedPaperIds: session.attachedPaperIds,
                attachedNoteIds: session.attachedNoteIds,
              }
            : session))
        }).catch(() => undefined)
        void reconcileProjection().catch(() => undefined)
        return
      }
      setActionMessage('')
      setActiveMessages((current) => [...current, {
        id: messageId('chat-error'),
        role: 'assistant',
        text: `真实文献对话失败：${error instanceof Error ? error.message : '未知错误'}`,
      }])
      void reconcileProjection().catch(() => undefined)
    }).finally(() => {
      if (streamAbortRef.current === controller) streamAbortRef.current = null
      setStreaming(false)
    })
  }

  async function stopGeneration() {
    if (!streaming) return
    stopRequestedRef.current = true
    setActionMessage('正在停止本轮生成…')
    try {
      await stopBackendChat(activeSessionId)
    } catch (error) {
      setActionMessage(`停止请求失败：${error instanceof Error ? error.message : '未知错误'}`)
    } finally {
      streamAbortRef.current?.abort()
    }
  }

  function compactContext() {
    if (backendMode !== 'connected') {
      setActionMessage(`真实后端未连接：${backendError || '不能整理上下文'}`)
      return
    }
    void compactBackendSession(activeSessionId).then((result) => {
        const stored = mapBackendSession(result.session)
        setSessions((current) => current.map((session) => session.id === stored.id ? {
          ...stored,
          attachedPaperIds: activeSession.attachedPaperIds,
          attachedNoteIds: activeSession.attachedNoteIds,
          contextPercent: stored.contextPercent,
        } : session))
        setActionMessage(`已追加续接摘要，原始 ${result.summarized_message_count} 条消息保持不变。`)
      }).catch((error) => {
        setActionMessage(`上下文压缩失败：${error instanceof Error ? error.message : '未知错误'}`)
      })
  }

  return (
    <div
      className={`app-shell${dragActive ? ' is-dragging' : ''}${hudLayoutActive ? ' hud-layout' : ''}`}
      data-skin-slot="literature-shell"
      data-app-surface="literature"
      onDragEnter={(event) => {
        event.preventDefault()
        if (Array.from(event.dataTransfer.types).includes('Files')) {
          dragDepthRef.current += 1
          setDragActive(true)
        }
      }}
      onDragOver={(event) => event.preventDefault()}
      onDragLeave={(event) => {
        event.preventDefault()
        dragDepthRef.current = Math.max(0, dragDepthRef.current - 1)
        if (dragDepthRef.current === 0) setDragActive(false)
      }}
      onDrop={(event) => {
        event.preventDefault()
        dragDepthRef.current = 0
        setDragActive(false)
        handleFiles(event.dataTransfer.files)
      }}
    >
      <div className="skin-background-layer" aria-hidden />
      <div className="skin-decoration-overlay" aria-hidden />
      {hudLayoutActive && (
        <SkinChrome
          themeId={themeId}
          customSkin={customSkin}
          projectName={projectInfo?.name || '文献智库'}
          projectPath={projectInfo?.root_path || '等待固定结构文献项目'}
          modelName="LITERATURE PROFILE"
          streaming={streaming}
          status={backendMode === 'connected' ? 'READY' : backendMode === 'connecting' ? 'CONNECTING' : 'OFFLINE'}
        />
      )}
      <nav className="activity-bar" data-skin-slot="activity-navigation" aria-label="主活动栏">
        <div className="activity-bar-top">
          <button
            type="button"
            className="activity-btn"
            title="功能大厅"
            onClick={() => {
              localStorage.removeItem(SKIN_RUNTIME_GUARD_KEY)
              window.location.assign(applicationHomeUrl(window.location.href))
            }}
          >
            <span className="activity-icon" aria-hidden>⌂</span>
          </button>
        </div>
        <div className="activity-bar-bottom">
          <button
            type="button"
            className="activity-btn"
            disabled={streaming}
            onClick={() => {
              localStorage.removeItem(SKIN_RUNTIME_GUARD_KEY)
              window.location.assign(workbenchSettingsUrl(window.location.href, 'literature'))
            }}
            title={streaming ? '请先停止当前生成' : '打开全局设置'}
          >
            <span className="activity-icon skin-icon" data-skin-icon="settings">⚙</span>
          </button>
        </div>
      </nav>
      <header className="topbar" data-skin-slot="literature-chrome">
        <div className="brand-mark"><Icon name="book" /></div>
        <div className="brand-copy">
          <strong>WORKMODE / LITERA</strong>
          <span>轻量文献智库工作台</span>
        </div>
        <button className="project-heading" type="button" onClick={() => void openProjectManager()} title="切换或新建文献项目">
          <span className="eyebrow">当前项目</span>
          <strong>{projectInfo?.name || '等待文献项目'}</strong>
          <span className="project-heading-action">管理项目</span>
        </button>
        <div className="topbar-spacer" />
      </header>

      <main className="workspace" data-skin-slot="literature-workspace">
        <aside className="library-panel" data-skin-slot="literature-library">
          <div className="library-panel-header">
            <button
              className="library-project-selector"
              type="button"
              onClick={() => void openProjectManager()}
              title="切换或管理项目"
            >
              <span>当前项目</span>
              <strong>{projectInfo?.name || '等待项目'}</strong>
              <em aria-hidden>⌄</em>
            </button>
            <div className="library-panel-meta">
              <span className="library-paper-count">{papers.length} 篇</span>
              <details className="library-more-menu">
                <summary aria-label="更多项目操作" title="更多项目操作">•••</summary>
                <div>
                  <button
                    type="button"
                    onClick={(event) => {
                      event.currentTarget.closest('details')?.removeAttribute('open')
                      void openProjectManager()
                    }}
                  >
                    <Icon name="layers" />管理项目
                  </button>
                  <button
                    type="button"
                    onClick={(event) => {
                      event.currentTarget.closest('details')?.removeAttribute('open')
                      void openPaperTrash()
                    }}
                  >
                    <Icon name="trash" />文献回收站
                  </button>
                </div>
              </details>
            </div>
          </div>

          <div className="library-toolbar">
            <label className="search-box">
              <Icon name="search" />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="搜索标题、作者、期刊、DOI…"
              />
            </label>

            <div className="library-command-row">
              <label className="literature-group-filter">
                <select
                  aria-label="按文献分组筛选"
                  value={selectedGroupId}
                  onChange={(event) => setSelectedGroupId(event.target.value)}
                >
                  <option value="">全部分组</option>
                  {literatureGroups.map((group) => <option key={group.id} value={group.id}>{group.name}</option>)}
                </select>
              </label>

              <div className="tag-filter-control">
                <button
                  className={`tag-filter-trigger${tagFilterOpen ? ' active' : ''}`}
                  onClick={() => setTagFilterOpen((open) => !open)}
                  type="button"
                >
                  <Icon name="filter" />
                  <span>标签筛选</span>
                  {selectedTagIds.length > 0 && <em>{selectedTagIds.length}</em>}
                </button>
              </div>

              <details className="library-import-menu">
                <summary aria-label="导入文献">
                  <Icon name="file" />
                  <span>导入</span>
                </summary>
                <div>
                  <button
                    disabled={backendMode !== 'connected' || streaming}
                    onClick={(event) => {
                      event.currentTarget.closest('details')?.removeAttribute('open')
                      fileInputRef.current?.click()
                    }}
                    type="button"
                  >
                    <Icon name="paperclip" />
                    <span><strong>导入 PDF</strong><small>选择一篇或多篇论文</small></span>
                  </button>
                  <button
                    disabled={backendMode !== 'connected'}
                    onClick={(event) => {
                      event.currentTarget.closest('details')?.removeAttribute('open')
                      openEndNoteImport()
                    }}
                    type="button"
                  >
                    <Icon name="file" />
                    <span><strong>导入 EndNote</strong><small>带入分组、标签和附件</small></span>
                  </button>
                </div>
              </details>
            </div>

            {tagFilterOpen && (
              <div className="tag-filter-popover">
                <label className="tag-search">
                  <Icon name="search" />
                  <input
                    value={tagQuery}
                    onChange={(event) => setTagQuery(event.target.value)}
                    placeholder="搜索标签或别名"
                    autoFocus
                  />
                </label>

                {tagQuery.trim() ? (
                  <div className="tag-search-results">
                    {tagSearchResults.length ? tagSearchResults.map((tag) => (
                      <label key={tag.id}>
                        <input
                          type="checkbox"
                          checked={selectedTagIds.includes(tag.id)}
                          onChange={() => toggleTagFilter(tag.id)}
                        />
                        <span>{tag.name}</span>
                        <small>{tagGroups.find((group) => group.id === tag.group_id)?.name ?? '未分类'}</small>
                      </label>
                    )) : <p>没有匹配标签</p>}
                  </div>
                ) : (
                  <div className="tag-category-list">
                    {tagGroups.map((group) => {
                      const groupTags = tagRegistry.filter((tag) => tag.group_id === group.id)
                      const selectedCount = groupTags.filter((tag) => selectedTagIds.includes(tag.id)).length
                      return (
                        <details key={group.id}>
                          <summary>
                            <span><strong style={{ color: group.color }}>{group.name}</strong><small>{groupTags.length} 个标签</small></span>
                            {selectedCount > 0 && <em>{selectedCount}</em>}
                          </summary>
                          <div>
                            {groupTags.length ? groupTags.map((tag) => (
                              <label key={tag.id}>
                                <input
                                  type="checkbox"
                                  checked={selectedTagIds.includes(tag.id)}
                                  onChange={() => toggleTagFilter(tag.id)}
                                />
                                <span>{tag.name}</span>
                                {tag.status === 'provisional' && <small>候选</small>}
                              </label>
                            )) : <p>当前项目暂无此类标签</p>}
                          </div>
                        </details>
                      )
                    })}
                  </div>
                )}
              </div>
            )}

            {selectedTagIds.length > 0 && (
              <div className="selected-filter-tags">
                {selectedTagIds.map((tagId) => {
                  const tag = tagRegistry.find((item) => item.id === tagId)
                  return tag ? (
                    <button key={tag.id} onClick={() => toggleTagFilter(tag.id)}>{tag.name}<Icon name="close" /></button>
                  ) : null
                })}
                <button className="clear-all-tags" onClick={() => setSelectedTagIds([])}>清除全部</button>
              </div>
            )}
          </div>

          <div className="paper-list" aria-label="文献列表">
            {filteredPapers.map((paper) => {
              const attached = activeSession.attachedPaperIds.includes(paper.id)
              return (
                <article className="paper-row" data-skin-slot="literature-paper" key={paper.id} onClick={() => openPaperDetail(paper.id)}>
                  <button
                    aria-label={attached ? `从对话移除 ${paper.title}` : `加入对话 ${paper.title}`}
                    className={`context-check${attached ? ' checked' : ''}`}
                    onClick={(event) => {
                      event.stopPropagation()
                      togglePaperAttachment(paper.id)
                    }}
                    title={attached ? '已加入对话上下文' : '加入对话上下文'}
                  >
                    {attached && <Icon name="check" />}
                  </button>
                  <div className="paper-main">
                    <h2>{paper.title}</h2>
                    {(paper.year || paper.journal) && (
                      <div className="paper-card-meta">
                        {paper.journal && <span>{paper.journal}</span>}
                        {paper.year && <span className="card-year">{paper.year}</span>}
                      </div>
                    )}
                    {(paper.groupIds.length > 0 || paper.tagIds.length > 0) && (
                      <div className="paper-classifiers">
                        {paper.groupIds.length > 0 && (
                          <div className="card-groups">
                            {paper.groupIds.slice(0, 1).map((groupId) => (
                              <span key={groupId}>{literatureGroups.find((group) => group.id === groupId)?.name || groupId}</span>
                            ))}
                            {paper.groupIds.length > 1 && <span>+{paper.groupIds.length - 1}</span>}
                          </div>
                        )}
                        <div className="card-tags">
                          {paper.tagIds.slice(0, 3).map((tagId) => {
                            const tag = tagRegistry.find((item) => item.id === tagId)
                            return tag ? <span className={tag.status === 'provisional' ? 'provisional' : ''} key={tag.id}>{tag.name}</span> : null
                          })}
                          {paper.tagIds.length > 3 && <span className="tag-overflow">+{paper.tagIds.length - 3}</span>}
                        </div>
                      </div>
                    )}
                  </div>
                </article>
              )
            })}
          </div>
        </aside>

        <section className="conversation-panel" data-skin-slot="literature-conversation">
          <div className="conversation-header" data-skin-slot="chat-header">
            <div>
              <span className="eyebrow">RESEARCH CONVERSATION</span>
            </div>
            <div className="session-switcher">
              <span>SESSION</span>
              <select value={activeSessionId} onChange={(event) => setActiveSessionId(event.target.value)} disabled={streaming}>
                {sessions.map((session) => <option value={session.id} key={session.id}>{session.name}</option>)}
              </select>
              <button className="session-rename-button" onClick={openSessionRename} aria-label="重命名当前会话" title="重命名当前会话" disabled={backendMode !== 'connected' || streaming}>✎</button>
              <button className="session-new-button" onClick={createSession} aria-label="新建 session" title="新建 session" disabled={backendMode !== 'connected' || streaming}>＋</button>
            </div>
            <div className="context-meter" title="正式 Workmode 上下文预算占用估算">
              <div className="context-copy"><span>上下文</span><strong>{activeSession.contextPercent}%</strong></div>
              <div className="meter-track"><span style={{ width: `${activeSession.contextPercent}%` }} /></div>
            </div>
            <button className="compact-button" onClick={compactContext} disabled={backendMode !== 'connected' || streaming}>
              <Icon name="layers" /> 整理上下文
            </button>
            <button className="memory-button" onClick={() => setMemoryOpen(true)} disabled={backendMode !== 'connected'}>
              <Icon name="memory" />
              <span>项目记忆</span>
            </button>
            <button className="notes-button" onClick={() => setNotesOpen(true)} title="项目笔记" disabled={backendMode !== 'connected'}>
              <Icon name="book" />
              <span>笔记</span>
              <em>{notes.length}</em>
            </button>
          </div>

          <div
            className="message-stream"
            data-skin-slot="message-stream"
            ref={messageStreamRef}
            onScroll={handleMessageStreamScroll}
          >
            <div className="date-divider"><span>当前会话</span></div>
            {backendMode === 'unavailable' && (
              <div className="backend-error-state" role="alert">
                <strong>真实后端没有连接成功</strong>
                <p>{backendError || '无法读取连接错误。请确认正式 Workmode 后端与文献项目已经启动。'}</p>
                <small>静态文献、演示消息和模拟回复已移除；连接恢复前不会产生任何假数据。</small>
              </div>
            )}
            {activeSession.messages.map((message) => (
              <div className={`message-block ${message.role}`} data-skin-slot={message.role === 'tool' ? 'tool-call' : 'message'} key={message.id}>
                {message.role === 'tool' ? (
                  <div className={`tool-event-card ${message.toolStatus || 'completed'}`}>
                    <div className="tool-event-heading">
                      <span className="tool-event-icon"><Icon name={message.toolStatus === 'failed' ? 'close' : message.toolStatus === 'running' ? 'clock' : 'check'} /></span>
                      <strong>{message.toolName || 'unknown_tool'}</strong>
                      <em>{message.toolStatus === 'failed' ? '失败' : message.toolStatus === 'running' ? '运行中' : message.toolStatus === 'cancelled' ? '已停止' : '完成'}</em>
                    </div>
                    <details>
                      <summary>查看参数和结果</summary>
                      <span>参数</span>
                      <pre>{JSON.stringify(message.toolArgs || {}, null, 2)}</pre>
                      <span>结果</span>
                      <pre>{message.text}</pre>
                    </details>
                  </div>
                ) : (
                  <>
                    {message.role !== 'system' && (
                      <div className="speaker-mark">{message.role === 'assistant' ? <Icon name="sparkles" /> : '你'}</div>
                    )}
                    <div className="message-body">
                      {message.role !== 'system' && <span className="speaker-name">{message.role === 'assistant' ? 'AI 文献助手' : 'YOU'}</span>}
                      <div className="message-bubble">
                        {message.role === 'assistant'
                          ? <div className="message-markdown"><MarkdownRenderer>{message.text}</MarkdownRenderer></div>
                          : <p>{message.text}</p>}
                        {message.interrupted && <span className="message-interrupted">已停止生成</span>}
                      </div>
                      {message.paperIds && (
                        <div className="inline-papers">
                          {message.paperIds.map((id) => {
                            const paper = papers.find((item) => item.id === id)
                            return paper ? <span key={id}><Icon name="file" /> {paper.filename}</span> : null
                          })}
                        </div>
                      )}
                      {message.noteIds && (
                        <div className="inline-papers inline-notes">
                          {message.noteIds.map((id) => {
                            const note = notes.find((item) => item.id === id)
                            return note ? <span key={id}><Icon name="book" /> {note.filename}</span> : null
                          })}
                        </div>
                      )}
                      {(message.sources?.length || message.noteSources?.length) && (
                        <div className="source-strip">
                          <span>依据</span>
                          {message.sources?.map((id) => {
                            const paper = papers.find((item) => item.id === id)
                            return paper ? (
                              <button key={id} onClick={() => openPaperDetail(id, 'facts')}>
                                {paper.title}
                              </button>
                            ) : null
                          })}
                          {message.noteSources?.map((id) => {
                            const note = notes.find((item) => item.id === id)
                            return note ? (
                              <button
                                className="note-source"
                                key={id}
                                onClick={() => {
                                  setActiveNoteId(id)
                                  setNotesOpen(true)
                                  setNoteMode('preview')
                                }}
                              >
                                笔记 · {note.title}
                              </button>
                            ) : null
                          })}
                        </div>
                      )}
                    </div>
                  </>
                )}
              </div>
            ))}
          </div>
          {showBackToLatest && (
            <button type="button" className="literature-back-to-latest" onClick={() => scrollToLatest('smooth')}>
              回到最新 ↓
            </button>
          )}

          <div className="composer-wrap" data-skin-slot="composer">
            {actionMessage && <div className="action-message" role="status">{actionMessage}</div>}
            {(attachedPapers.length > 0 || attachedNotes.length > 0) && (
              <div className="attachment-tray">
                <span className="tray-label">对话资料</span>
                {attachedPapers.map((paper) => (
                  <span className="attachment-chip" key={paper.id}>
                    <Icon name="file" />
                    <span>{paper.title}</span>
                    <button onClick={() => togglePaperAttachment(paper.id)} aria-label={`移除 ${paper.title}`}><Icon name="close" /></button>
                  </span>
                ))}
                {attachedNotes.map((note) => (
                  <span className="attachment-chip note-chip" key={note.id}>
                    <Icon name="book" />
                    <span>{note.title}</span>
                    <button onClick={() => toggleNoteAttachment(note.id)} aria-label={`移除 ${note.title}`}><Icon name="close" /></button>
                  </span>
                ))}
              </div>
            )}
            <div className="composer">
              <button className="attach-button" onClick={() => fileInputRef.current?.click()} aria-label="添加 PDF" disabled={backendMode !== 'connected' || streaming}>
                <Icon name="paperclip" />
              </button>
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.ctrlKey && event.key === 'Enter') {
                    event.preventDefault()
                    sendMessage()
                  }
                }}
                placeholder="拖入 PDF，或告诉 AI 你想讨论什么…"
                rows={2}
                disabled={backendMode !== 'connected' || streaming}
              />
              <button
                className={`send-button${streaming ? ' stop' : ''}`}
                onClick={streaming ? () => void stopGeneration() : sendMessage}
                disabled={backendMode !== 'connected' || (!streaming && !input.trim())}
                aria-label={streaming ? '停止生成' : '发送'}
              >
                <Icon name={streaming ? 'close' : 'send'} />
              </button>
              <input
                ref={fileInputRef}
                type="file"
                accept="application/pdf,.pdf"
                multiple
                hidden
                onChange={(event) => {
                  if (event.target.files) handleFiles(event.target.files)
                  event.target.value = ''
                }}
              />
            </div>
            <div className="composer-hint"><span>Ctrl + Enter 发送</span><span>{backendMode === 'connected' ? '选中一篇后说“精读这篇”，默认逐图讲解' : '等待真实后端连接，不提供静态预览或模拟回复'}</span></div>
          </div>
        </section>

      </main>

      {projectManagerOpen && (
        <div className="modal-backdrop centered-dialog-backdrop" role="presentation" onMouseDown={() => {
          if (projectOptions.length && !projectActionBusy) setProjectManagerOpen(false)
        }}>
          <section
            aria-labelledby="literature-project-manager-title"
            aria-modal="true"
            className="literature-project-manager-modal"
            data-skin-slot="literature-project-manager"
            role="dialog"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header className="modal-header">
              <div><span className="eyebrow">LIBRARIES</span><h2 id="literature-project-manager-title">文献项目</h2></div>
              <button
                disabled={!projectOptions.length || projectActionBusy}
                onClick={() => setProjectManagerOpen(false)}
                aria-label="关闭项目管理"
              ><Icon name="close" /></button>
            </header>
            <div className="literature-project-manager-body">
              <div className="literature-project-list">
                {projectOptions.map((project) => (
                  <article className={project.slug === projectInfo?.slug ? 'active' : ''} key={project.slug}>
                    {editingProjectSlug === project.slug ? (
                      <form className="literature-project-rename" onSubmit={(event) => void commitProjectRename(event)}>
                        <input
                          value={editingProjectName}
                          maxLength={120}
                          autoFocus
                          onChange={(event) => setEditingProjectName(event.target.value)}
                        />
                        <button type="submit" disabled={projectActionBusy || !editingProjectName.trim()}>保存</button>
                        <button type="button" disabled={projectActionBusy} onClick={() => setEditingProjectSlug(null)}>取消</button>
                      </form>
                    ) : (
                      <>
                        <button className="literature-project-open" type="button" onClick={() => void switchLiteratureProject(project.slug)}>
                          <span><strong>{project.name}</strong><small>{project.root_path}</small></span>
                          <em>{project.storage_mode === 'managed' ? '托管项目' : '旧版外部项目'}</em>
                        </button>
                        <div className="literature-project-row-actions">
                          <button type="button" disabled={projectActionBusy} onClick={() => startProjectRename(project)}>重命名</button>
                          <button type="button" className="danger" disabled={projectActionBusy || streaming} onClick={() => void removeLiteratureProject(project)}>移除</button>
                        </div>
                      </>
                    )}
                  </article>
                ))}
                {!projectOptions.length && <p className="literature-project-empty">还没有文献项目。输入名称即可创建，无需选择文件夹。</p>}
              </div>

              <form className="literature-project-create" onSubmit={(event) => void createManagedProject(event)}>
                <label htmlFor="literature-project-name">新建文献项目</label>
                <div>
                  <input
                    id="literature-project-name"
                    value={newProjectName}
                    maxLength={120}
                    placeholder="例如：EPR 缺陷化学文献库"
                    autoFocus={!projectOptions.length}
                    onChange={(event) => setNewProjectName(event.target.value)}
                  />
                  <button type="submit" disabled={projectActionBusy || !newProjectName.trim()}>{projectActionBusy ? '处理中…' : '创建'}</button>
                </div>
                <small>Windows 默认保存在 D:\workmode\项目名；没有 D 盘时自动使用用户目录。旧版外部项目保持原位置。</small>
              </form>
              {projectManagerError && <p className="literature-project-manager-error" role="alert">{projectManagerError}</p>}
            </div>
          </section>
        </div>
      )}

      {renameSessionOpen && (
        <div className="modal-backdrop centered-dialog-backdrop" role="presentation" onMouseDown={() => {
          if (!renamingSession) setRenameSessionOpen(false)
        }}>
          <section
            aria-labelledby="rename-session-title"
            aria-modal="true"
            className="session-rename-modal"
            data-skin-slot="session-rename"
            role="dialog"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header className="modal-header">
              <div><span className="eyebrow">SESSION</span><h2 id="rename-session-title">重命名会话</h2></div>
              <button disabled={renamingSession} onClick={() => setRenameSessionOpen(false)} aria-label="关闭重命名窗口"><Icon name="close" /></button>
            </header>
            <form className="session-rename-form" onSubmit={(event) => void renameActiveSession(event)}>
              <label htmlFor="literature-session-title">会话名称</label>
              <input
                id="literature-session-title"
                value={renameSessionTitle}
                maxLength={80}
                autoFocus
                onChange={(event) => setRenameSessionTitle(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Escape' && !renamingSession) setRenameSessionOpen(false)
                }}
              />
              <small>{renameSessionTitle.trim().length}/80</small>
              <div className="session-rename-actions">
                <button type="button" disabled={renamingSession} onClick={() => setRenameSessionOpen(false)}>取消</button>
                <button type="submit" disabled={renamingSession || !renameSessionTitle.trim()}>{renamingSession ? '保存中…' : '保存'}</button>
              </div>
            </form>
          </section>
        </div>
      )}

      {trashOpen && (
        <div className="modal-backdrop centered-dialog-backdrop" role="presentation" onMouseDown={() => {
          if (!trashBusyId) setTrashOpen(false)
        }}>
          <section
            aria-labelledby="literature-trash-title"
            aria-modal="true"
            className="literature-trash-modal"
            data-skin-slot="literature-trash"
            role="dialog"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header className="modal-header">
              <div><span className="eyebrow">RECYCLE BIN</span><h2 id="literature-trash-title">文献回收站</h2></div>
              <button disabled={Boolean(trashBusyId)} onClick={() => setTrashOpen(false)} aria-label="关闭文献回收站"><Icon name="close" /></button>
            </header>
            <div className="literature-trash-body">
              {deletedPapers.length ? deletedPapers.map((entry) => (
                <article key={entry.trash_id}>
                  <Icon name="file" />
                  <div>
                    <strong>{entry.paper.title}</strong>
                    <span>{entry.paper.original_filename}</span>
                    <small>删除于 {entry.deleted_at ? new Date(entry.deleted_at).toLocaleString() : '未知时间'} · {entry.file_count} 组材料</small>
                  </div>
                  <button disabled={Boolean(trashBusyId)} onClick={() => void restoreDeletedPaper(entry)}>
                    <Icon name="restore" />{trashBusyId === entry.trash_id ? '恢复中…' : '恢复'}
                  </button>
                </article>
              )) : <div className="literature-trash-empty"><Icon name="trash" /><strong>回收站是空的</strong><span>移除的文献会连同 PDF 与解析产物一起保存在这里。</span></div>}
              {trashError && <p className="literature-trash-error" role="alert">{trashError}</p>}
            </div>
          </section>
        </div>
      )}

      {detailPaper && (
        <div className="modal-backdrop centered-dialog-backdrop" role="presentation" onMouseDown={() => setDetailPaperId(null)}>
          <section
            aria-label="文献详细信息"
            aria-modal="true"
            className="paper-detail-modal"
            data-skin-slot="literature-detail"
            role="dialog"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header className="modal-header">
              <div>
                <span className="eyebrow">PAPER RECORD</span>
                <h2>{detailPaper.archiveFilename ?? detailPaper.filename}</h2>
              </div>
              <div className="paper-detail-header-actions">
                <button onClick={() => void openPaperSiFolder(detailPaper.id)}>
                  <Icon name="layers" />打开 SI 文件夹
                </button>
                <button className="paper-delete-button" disabled={streaming || trashBusyId === detailPaper.id} onClick={() => void deleteDetailPaper()}>
                  <Icon name="trash" />{trashBusyId === detailPaper.id ? '处理中…' : '移入回收站'}
                </button>
                <button onClick={() => setDetailPaperId(null)} aria-label="关闭文献详情"><Icon name="close" /></button>
              </div>
            </header>
            <nav className="paper-detail-tabs" aria-label="文献详情页签">
              <button className={detailTab === 'overview' ? 'active' : ''} onClick={() => setDetailTab('overview')}>概览与提炼</button>
              <button className={detailTab === 'facts' ? 'active' : ''} onClick={() => setDetailTab('facts')}>完整客观事实 <span>{detailPaper.factReport.length}</span></button>
              <button className={detailTab === 'pdf' ? 'active' : ''} onClick={() => setDetailTab('pdf')}>原始 PDF</button>
            </nav>

            {detailTab === 'overview' && (
              <div className="modal-scroll">
                <div className="paper-detail-heading">
                  <span className={`status-badge status-${detailPaper.status}`}><StatusDot status={detailPaper.status} /> {statusLabel(detailPaper.status)}</span>
                  <h1>{detailPaper.title}</h1>
                  <p>{detailPaper.authors}</p>
                  {detailPaper.metadataTrust !== 'complete' && (
                    <div className="metadata-review-notice" role="status">
                      <strong>元数据待人工确认</strong>
                      <span>{detailPaper.metadataIssue || '首页没有找到可逐字核验的 Cite This 元数据。客观事实报告仍会继续生成；请在下方补齐作者、年份和期刊后完成标准命名。'}</span>
                    </div>
                  )}
                  <div className="detail-metadata">
                    <span className={!detailPaper.archiveFilename ? 'metadata-pending' : ''}>
                      <strong>标准档名</strong>{detailPaper.archiveFilename ?? '等待首页元数据确认'}
                      <small>若同名已存在，依次追加 _2、_3，不覆盖原文件。</small>
                    </span>
                    <span><strong>原始导入名</strong>{detailPaper.filename}</span>
                    <span><strong>归档位置</strong>{detailPaper.archiveLocation}/</span>
                    <span><strong>元数据来源</strong>{METADATA_SOURCE_LABELS[detailPaper.metadataSource]}</span>
                    <span><strong>发表日期</strong>{detailPaper.publicationDate || detailPaper.year || '未填写'}</span>
                    <span><strong>期刊</strong>{detailPaper.journal || '未填写'}</span>
                    <span><strong>DOI</strong>{detailPaper.doi || '未填写'}</span>
                    <span><strong>第一作者姓</strong>{detailPaper.firstAuthorSurname || '未填写'}</span>
                    <span><strong>期刊缩写</strong>{detailPaper.journalAbbreviation || '未填写'}</span>
                    <span><strong>文献分组</strong>{detailPaper.groupIds.map((id) => literatureGroups.find((group) => group.id === id)?.name || id).join(' · ') || '未分组'}</span>
                    <span><strong>SI 文件夹</strong>{detailPaper.siFolder || '未登记'}</span>
                    <span><strong>处理阶段</strong>{detailPaper.processingStage || statusLabel(detailPaper.status)}</span>
                    <span><strong>处理错误</strong>{detailPaper.processingError || '无'}</span>
                  </div>
                  <div className="archive-contract">
                    <article>
                      <span>文章类型与主档模板</span>
                      <strong>{PAPER_TYPE_LABELS[detailPaper.paperType]}</strong>
                      <small>按标题、摘要自定位和数据来源判断，不按行数或引用数判断。</small>
                    </article>
                    <article>
                      <span>MinerU 产物目录</span>
                      <strong>{detailPaper.archiveLocation}/minerU识别结果/{(detailPaper.archiveFilename ?? detailPaper.filename).replace(/\.pdf$/i, '')}/</strong>
                      <small>full.md · images/ · layout.json · *_content_list.json</small>
                    </article>
                    <article>
                      <span>归档校验</span>
                      <strong>{VERIFICATION_LABELS[detailPaper.verificationStatus]}</strong>
                      <small>通过后同步更新处理结果索引。</small>
                    </article>
                  </div>
                  <div className="archive-flow" aria-label="文献入档流程">
                    <span className={detailPaper.archiveFilename ? 'done' : 'current'}><em>1</em>首页元数据与标准命名</span>
                    <span className={detailPaper.factReport.length ? 'done' : 'current'}><em>2</em>MinerU + 事实段 1–5</span>
                    <span className={detailPaper.archiveLocation === '文献/已处理' ? 'done' : 'current'}><em>3</em>主对话补跨文献段</span>
                    <span className={detailPaper.verificationStatus === 'passed' ? 'done' : ''}><em>4</em>校验并更新索引</span>
                  </div>
                </div>

                <div className="detail-grid">
                  <section className="detail-section summary-section">
                    <div className="section-title"><span>AI 提炼摘要</span><em>SYNTHESIS</em></div>
                    <p>{detailPaper.summary || '等待正文解析和讨论完成后生成。'}</p>
                  </section>

                  <section className="detail-section focus-section">
                    <div className="section-title"><span>用户关注点</span><em>FOCUS</em></div>
                    <p className="focus-note">{detailPaper.focus || '尚未记录用户关注点。'}</p>
                  </section>

                  <section className="detail-section facts-section">
                    <div className="section-title"><span>事实报告摘要</span><em>REPORT INDEX</em></div>
                    <ol className="fact-list">
                      {(detailPaper.facts.length ? detailPaper.facts : ['等待 MinerU 和客观事实抽取流水线完成。']).map((fact) => <li key={fact}>{fact}</li>)}
                    </ol>
                    <button className="open-full-report" onClick={() => setDetailTab('facts')}>阅读完整客观事实报告</button>
                  </section>

                  <section className="detail-section tags-section">
                    <div className="section-title"><span>文章标签</span><em>SEMI-OPEN</em></div>
                    <div className="paper-tags">
                      {detailPaper.tagIds.map((tagId) => {
                        const tag = tagRegistry.find((item) => item.id === tagId)
                        return tag ? <span className={tag.status === 'provisional' ? 'provisional' : ''} key={tag.id}>{tag.name}{tag.status === 'provisional' && ' · 候选'}</span> : null
                      })}
                    </div>
                    <p className="muted-copy">正式标签用于稳定筛选；新概念先作为候选标签，确认后再进入对应标签集。</p>
                  </section>
                </div>
                {backendMode === 'connected' && detailPaper.archiveLocation !== '文献/已处理' && (
                  <section className="review-confirm-panel">
                    <div className="section-title"><span>文献入档信息</span><em>DIRECT WRITE</em></div>
                    <label>
                      <span>文章标签</span>
                      <input
                        value={reviewTagsDraft}
                        onChange={(event) => setReviewTagsDraft(event.target.value)}
                        placeholder="EPR，氧空位，原位表征"
                      />
                      <small>逗号分隔；命中白名单或别名时复用，未知标签先登记为候选。</small>
                    </label>
                    <label>
                      <span>用户关注点</span>
                      <textarea value={reviewFocusDraft} onChange={(event) => setReviewFocusDraft(event.target.value)} rows={3} />
                    </label>
                    <label>
                      <span>笔记摘要</span>
                      <textarea value={reviewSummaryDraft} onChange={(event) => setReviewSummaryDraft(event.target.value)} rows={4} />
                    </label>
                    <button onClick={() => void confirmPaperReview()}>保存文献记录</button>
                    {actionMessage && <p className="inline-action-message">{actionMessage}</p>}
                  </section>
                )}
              </div>
            )}

            {detailTab === 'facts' && (
              <div className="fact-report-workspace">
                <aside className="fact-report-index">
                  <span className="eyebrow">REPORT OUTLINE</span>
                  <h3>客观事实抽取报告</h3>
                  <p>完整保留数据、条件、作者归属与原始段落定位。</p>
                  <nav>
                    {detailPaper.factReport.map((section, index) => (
                      <button
                        className={section.owner === 'main_conversation' ? 'locked-section' : ''}
                        key={section.id}
                        onClick={() => document.getElementById(`fact-${detailPaper.id}-${section.id}`)?.scrollIntoView({ behavior: 'smooth', block: 'start' })}
                      >
                        <span>{String(index + 1).padStart(2, '0')}</span>{section.title}{section.owner === 'main_conversation' && <em>主对话</em>}
                      </button>
                    ))}
                  </nav>
                </aside>
                <article className="fact-report-scroll">
                  <header className="fact-report-heading">
                    <span className="eyebrow">FULL OBJECTIVE FACTS</span>
                    <h1>{detailPaper.title}</h1>
                    <p>这里承载完整事实报告，不受聊天气泡或摘要长度限制。生产版直接渲染对应的 `_客观事实抽取报告.md`。</p>
                    <div className="fact-report-discipline">
                      <span>DeepSeek / Subagent 仅写 1–5 段</span>
                      <span>第 6 段仅主对话讨论后填写</span>
                      <span>页码以 *_content_list.json 的 page_idx 为准</span>
                    </div>
                  </header>
                  {backendMode === 'connected' && detailPaper.archiveLocation !== '文献/已处理' && (
                    <section className="cross-literature-editor">
                      <div className="section-title"><span>主对话：跨文献关系与系列归属</span><em>SECTION 6</em></div>
                      <textarea
                        value={crossLiteratureDraft}
                        onChange={(event) => setCrossLiteratureDraft(event.target.value)}
                        placeholder="结合当前项目与其他已处理文献，写明系列归属、关系、地位与影响。这里是主对话判断，不得写回客观事实段 1–5。"
                        rows={5}
                      />
                      <div className="archive-action-row">
                        <button onClick={() => void confirmCrossLiterature()}>写入第 6 段</button>
                        <button className="archive-button" onClick={() => void verifyAndArchivePaper()}>校验并归档</button>
                      </div>
                      {archiveVerification && !archiveVerification.ok && (
                        <ul className="archive-issues">
                          {archiveVerification.issues.map((issue) => <li key={issue}>{issue}</li>)}
                        </ul>
                      )}
                      {actionMessage && <p className="inline-action-message">{actionMessage}</p>}
                    </section>
                  )}
                  {factReportMarkdowns[detailPaper.id] ? (
                    <div className="backend-fact-markdown">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{factReportMarkdowns[detailPaper.id]}</ReactMarkdown>
                    </div>
                  ) : detailPaper.factReport.length ? detailPaper.factReport.map((section, sectionIndex) => (
                    <section id={`fact-${detailPaper.id}-${section.id}`} className={`fact-report-section${section.owner === 'main_conversation' ? ' locked' : ''}`} key={section.id}>
                      <h2><span>{sectionIndex + 1}</span>{section.title}{section.owner === 'main_conversation' && <em>仅主对话可填写</em>}</h2>
                      <div className="fact-report-entries">
                        {section.entries.map((entry, entryIndex) => (
                          <article key={`${section.id}-${entryIndex}`}>
                            <div>
                              <span className={`fact-kind kind-${entry.kind}`}>{FACT_KIND_LABELS[entry.kind]}</span>
                              {entry.location && <em>{entry.location}</em>}
                            </div>
                            <p>{entry.content}</p>
                          </article>
                        ))}
                      </div>
                    </section>
                  )) : (
                    <div className="empty-report"><Icon name="clock" /><strong>完整事实报告尚未生成</strong><span>流水线完成后将在这里显示全部章节与数据。</span></div>
                  )}
                </article>
              </div>
            )}

            {detailTab === 'pdf' && (
              <div className="pdf-workspace">
                <div className="pdf-toolbar">
                  <div><Icon name="file" /><span>{detailPaper.filename}</span></div>
                  <span>受控后端预览</span>
                </div>
                {pdfUrls[detailPaper.id] ? (
                  <PdfViewer className="pdf-frame" src={pdfUrls[detailPaper.id]} title={`${detailPaper.title} 原始 PDF`} />
                ) : (
                  <div className="pdf-empty">
                    <Icon name="file" />
                    <strong>当前记录没有可用的 PDF 预览</strong>
                    <p>原始 PDF 只通过受控后端端点显示；后端未连接时不提供静态或临时预览。</p>
                  </div>
                )}
              </div>
            )}
          </section>
        </div>
      )}

      {pendingImportFiles.length > 0 && (
        <div className="modal-backdrop" role="presentation" onMouseDown={() => {
          if (!importingPapers) setPendingImportFiles([])
        }}>
          <section
            aria-label="确认入库文献"
            aria-modal="true"
            className="import-confirm-modal"
            data-skin-slot="literature-import"
            role="dialog"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header className="modal-header">
              <div><span className="eyebrow">IMPORT PDF</span><h2>确认入库</h2></div>
              <button
                aria-label="取消入库"
                disabled={importingPapers}
                onClick={() => setPendingImportFiles([])}
              ><Icon name="close" /></button>
            </header>
            <div className="import-confirm-body">
              <p>以下 PDF 将写入当前文献项目。PDF 只会加入文献库，不会自动解析或加入当前对话：</p>
              <ul>
                {pendingImportFiles.map((file, index) => (
                  <li key={`${file.name}-${file.size}-${index}`}>
                    <Icon name="file" />
                    <span>{file.name}</span>
                    <em>{(file.size / 1024 / 1024).toFixed(2)} MB</em>
                  </li>
                ))}
              </ul>
              <small>只有点击确认后才会写入；重复内容会复用已有记录，不覆盖文件。</small>
            </div>
            <footer className="import-confirm-actions">
              <button disabled={importingPapers} onClick={() => setPendingImportFiles([])}>取消</button>
              <button disabled={importingPapers} onClick={() => void confirmPendingImport()}>
                {importingPapers ? '正在入库…' : `确认入库 ${pendingImportFiles.length} 篇`}
              </button>
            </footer>
          </section>
        </div>
      )}

      {endNoteOpen && (
        <div className="modal-backdrop centered-dialog-backdrop" role="presentation" onMouseDown={() => {
          if (!endNoteBusy) setEndNoteOpen(false)
        }}>
          <section
            className="endnote-import-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="endnote-import-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header className="modal-header">
              <div><span className="eyebrow">ENDNOTE IMPORT</span><h2 id="endnote-import-title">导入 EndNote 文献库</h2></div>
              <button disabled={endNoteBusy} onClick={() => setEndNoteOpen(false)} aria-label="关闭 EndNote 导入"><Icon name="close" /></button>
            </header>
            <div className="endnote-import-body">
              {!endNotePreview && !endNoteResult && (
                <>
                  <div className="endnote-intro">
                    <strong>把旧文献库直接搬进来</strong>
                    <p>EndNote 中可用的文献元数据、手工分组、标签、标签颜色和附件都会合并到当前项目。智能分组不会导入，原来的 EndNote 文件不会被修改。</p>
                  </div>
                  <div className="endnote-choice-grid">
                    <button disabled={endNoteBusy} onClick={() => void autoFindEndNote()}>
                      <Icon name="search" /><span><strong>{endNoteBusy ? '正在扫描本机所有磁盘…' : '自动查找'}</strong><small>扫描本机所有磁盘中的 .enl 和 .enlx，可能需要几十秒</small></span>
                    </button>
                    <button disabled={endNoteBusy} onClick={() => void manuallyChooseEndNote()}>
                      <Icon name="file" /><span><strong>手动选择</strong><small>自己选一个 EndNote 文献库文件</small></span>
                    </button>
                  </div>
                  {endNoteCandidates.length > 1 && (
                    <div className="endnote-candidate-list">
                      <strong>找到了 {endNoteCandidates.length} 个文献库，请选择一个：</strong>
                      {endNoteCandidates.map((candidate) => (
                        <button key={candidate.path} onClick={() => void loadEndNotePreview(candidate.path)}>
                          <span>{candidate.name}</span>
                          <small>
                            {candidate.has_data_folder
                              ? '完整工作库'
                              : candidate.type === 'enlx'
                                ? '压缩文献库'
                                : '未找到同名 .Data 文件夹'}
                            {candidate.variants.length > 1 ? ` · 同名文件 ${candidate.variants.length} 个` : ''}
                            {' · '}{candidate.path}
                          </small>
                        </button>
                      ))}
                    </div>
                  )}
                </>
              )}

              {endNotePreview && !endNoteResult && (
                <>
                  <div className="endnote-warning">
                    <Icon name="clock" />
                    <div><strong>导入前，请先关闭 EndNote</strong><span>EndNote 占用文献库时可能导致读取失败。关闭后再点“开始导入”即可。</span></div>
                  </div>
                  <dl className="endnote-preview-stats">
                    <div><dt>文献记录</dt><dd>{endNotePreview.reference_count}</dd></div>
                    <div><dt>可以导入</dt><dd>{endNotePreview.importable_count}</dd></div>
                    <div><dt>手工分组</dt><dd>{endNotePreview.manual_group_count}</dd></div>
                    <div><dt>标签</dt><dd>{endNotePreview.tag_count}</dd></div>
                    <div><dt>附件</dt><dd>{endNotePreview.attachment_count}</dd></div>
                    <div><dt>缺少主 PDF</dt><dd>{endNotePreview.failed_count}</dd></div>
                  </dl>
                  <p className="endnote-source-path">{endNotePreview.source_path}</p>
                  <p className="endnote-import-note">每条文献会从全部附件中寻找第一个有效 PDF 作为主论文；其他附件放进该文献的 SI 文件夹。没有有效 PDF 的记录会单独报错，不影响其余文献。</p>
                </>
              )}

              {endNoteResult && (
                <>
                  <div className="endnote-result-summary">
                    <Icon name="check" />
                    <div><strong>导入完成</strong><span>成功 {endNoteResult.imported_count} 篇，失败 {endNoteResult.failed_count} 篇；导入过程没有调用 AI。</span></div>
                  </div>
                  {endNoteResult.failures.length > 0 && (
                    <div className="endnote-failures">
                      <strong>这些记录没有导入：</strong>
                      {endNoteResult.failures.map((failure) => (
                        <p key={failure.endnote_record_id}>{failure.title || `记录 ${failure.endnote_record_id}`}：{failure.reason}</p>
                      ))}
                    </div>
                  )}
                  {duplicateResult ? (
                    <div className="endnote-duplicates">
                      <strong>查重结果：{duplicateResult.group_count} 组可能重复</strong>
                      <span>系统只列出结果，不会自动合并或覆盖。你可以稍后逐组手动处理。</span>
                    </div>
                  ) : (
                    <button className="endnote-dedupe-button" disabled={endNoteBusy} onClick={() => void scanDuplicatesAfterImport()}>
                      <Icon name="search" />导入完成后查重
                    </button>
                  )}
                </>
              )}

              {endNoteError && <p className="endnote-error">{endNoteError}</p>}
            </div>
            <footer className="endnote-import-actions">
              {endNotePreview && !endNoteResult ? (
                <>
                  <button disabled={endNoteBusy} onClick={() => {
                    setEndNotePreview(null)
                    setEndNotePath('')
                  }}>返回</button>
                  <button disabled={endNoteBusy || endNotePreview.importable_count === 0} onClick={() => void confirmEndNoteImport()}>
                    {endNoteBusy ? '正在导入…' : `开始导入 ${endNotePreview.importable_count} 篇`}
                  </button>
                </>
              ) : (
                <button disabled={endNoteBusy} onClick={() => setEndNoteOpen(false)}>
                  {endNoteResult ? '完成' : '取消'}
                </button>
              )}
            </footer>
          </section>
        </div>
      )}

      {memoryOpen && (
        <div className="modal-backdrop centered-dialog-backdrop" role="presentation" onMouseDown={() => setMemoryOpen(false)}>
          <section
            aria-label="项目记忆"
            aria-modal="true"
            className="memory-popover"
            data-skin-slot="literature-memory"
            role="dialog"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header className="modal-header compact-modal-header">
              <div className="memory-heading">
                <div className="memory-icon"><Icon name="memory" /></div>
                <div><span className="eyebrow">FIXED CONTEXT</span><h2>PROJECT_MEMORY.md</h2></div>
              </div>
              <button onClick={() => setMemoryOpen(false)} aria-label="关闭项目记忆"><Icon name="close" /></button>
            </header>
            <div className="memory-popover-body">
              <p className="memory-intro">当前项目的正式 Workmode 持久记忆；文献前端不维护第二份记忆。</p>
              <div className="memory-rules">
                {memoryState.projectMemory.map((memory, index) => (
                  <article key={`${memory}-${index}`}><span>{String(index + 1).padStart(2, '0')}</span><p>{memory}</p></article>
                ))}
              </div>
              <div className="memory-scope"><Icon name="check" /> 每轮固定注入 · 仅当前项目</div>
            </div>
          </section>
        </div>
      )}

      {notesOpen && activeNote && (
        <div className="modal-backdrop centered-dialog-backdrop" role="presentation" onMouseDown={() => setNotesOpen(false)}>
          <section
            aria-label="项目笔记工作区"
            aria-modal="true"
            className="notes-workspace-modal"
            data-skin-slot="literature-notes"
            role="dialog"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header className="modal-header notes-modal-header">
              <div>
                <span className="eyebrow">PROJECT NOTES</span>
                <h2>笔记工作区</h2>
              </div>
              <div className="notes-header-actions">
                <button onClick={createBlankNote}>＋ 新建笔记</button>
                <button onClick={() => setNotesOpen(false)} aria-label="关闭笔记工作区"><Icon name="close" /></button>
              </div>
            </header>

            <div className="notes-workspace-body">
              <aside className="notes-sidebar">
                <div className="notes-discipline">
                  <span><Icon name="memory" /> 来自 PROJECT_MEMORY.md</span>
                  {noteMaintenanceRules.map((rule) => <p key={rule}>{rule}</p>)}
                  <small>AI 可自主检索和读取笔记，并根据用户任务直接调用文献笔记工具写入。</small>
                </div>
                <div className="notes-list-heading"><span>项目笔记</span><em>{notes.length}</em></div>
                <div className="notes-list">
                  {notes.map((note) => {
                    const attached = activeSession.attachedNoteIds.includes(note.id)
                    return (
                      <article className={activeNote.id === note.id ? 'active' : ''} key={note.id} onClick={() => setActiveNoteId(note.id)}>
                        <button
                          className={`context-check${attached ? ' checked' : ''}`}
                          onClick={(event) => {
                            event.stopPropagation()
                            toggleNoteAttachment(note.id)
                          }}
                          title={attached ? '从当前 session 移除' : '加入当前 session 对话'}
                        >
                          {attached && <Icon name="check" />}
                        </button>
                        <div><strong>{note.title}</strong><span>{note.filename}</span><small>{note.updatedAt}</small></div>
                      </article>
                    )
                  })}
                </div>
              </aside>

              <main className="note-document-panel">
                <div className="note-document-toolbar">
                  <div><strong>{activeNote.title}</strong><span>{activeNote.filename} · {activeNote.updatedAt}</span></div>
                  <div className="note-mode-switch">
                    <button className={noteMode === 'edit' ? 'active' : ''} onClick={() => setNoteMode('edit')}>编辑 MD</button>
                    <button className={noteMode === 'preview' ? 'active' : ''} onClick={() => setNoteMode('preview')}>渲染预览</button>
                  </div>
                  <button onClick={downloadActiveNoteMarkdown}>导出 MD</button>
                  <button className="pdf-export-button" onClick={exportActiveNotePdf}>导出 PDF</button>
                  <button className="note-delete-button" onClick={() => void deleteActiveNote()}>删除笔记</button>
                  <button className="note-save-button" onClick={() => void saveActiveNote()}>保存</button>
                </div>

                {noteMode === 'edit' && (
                  <textarea
                    className="note-markdown-editor"
                    value={activeNote.markdown}
                    onChange={(event) => updateActiveNote(event.target.value)}
                    spellCheck={false}
                  />
                )}
                <div
                  className={`note-rendered-preview${noteMode === 'preview' ? '' : ' hidden-preview'}`}
                  ref={notePreviewRef}
                >
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{activeNote.markdown}</ReactMarkdown>
                </div>
              </main>
            </div>
          </section>
        </div>
      )}

      {projectInfo && <LiteratureOnboarding
        onConfigureMineru={() => {
          localStorage.removeItem(SKIN_RUNTIME_GUARD_KEY)
          window.location.assign(workbenchSettingsUrl(window.location.href, 'literature'))
        }}
      />}

      {dragActive && (
        <div className="drop-overlay">
          <div><Icon name="paperclip" /><strong>释放以加入当前文献项目</strong><span>只接受 PDF · 流式写入固定结构项目</span></div>
        </div>
      )}
    </div>
  )
}
