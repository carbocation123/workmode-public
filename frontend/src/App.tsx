import { useEffect, useMemo, useRef, useState } from 'react'
import {
  API_BASE,
  AppSettings,
  ContextUsage,
  FileContent,
  FileEntry,
  Message,
  Project,
  Session,
  api,
  getToken,
  setToken,
  streamChat
} from './api'
import {
  checkForDesktopUpdate,
  chooseAndMigrateLegacyPortable,
  getDesktopInfo,
  installDesktopUpdate
} from './desktop'
import {
  buildConversationItems,
  isNearBottom,
  type ToolConversationItem
} from './conversation'
import { directoryPaths, visibleFileEntries } from './fileTree'
import { MarkdownRenderer } from './MarkdownRenderer'
import {
  AchievementPanel,
  AchievementToast,
  FirstRunWizard,
  GuidedTour,
  TutorialChecklist,
  type ModelDraft
} from './OnboardingUI'
import {
  ACHIEVEMENTS,
  ONBOARDING_STORAGE_KEY,
  applyProductEvent,
  parseProgress,
  resetTutorialTasks,
  tutorialComplete,
  type AchievementDefinition,
  type ProductEvent,
  type TutorialTaskId
} from './onboarding'

type ActivePanel = 'project' | 'settings'
const SUMMARY_PREFIX = '<CONTEXT_SUMMARY>\n\n'

function fileDepth(path: string) {
  return Math.max(0, path.split('/').length - 1)
}

function isImage(path: string) {
  return /\.(png|jpe?g|gif|bmp|webp)$/i.test(path)
}

function isPdf(path: string) {
  return /\.pdf$/i.test(path)
}

function formatTokens(value?: unknown) {
  if (typeof value !== 'number') return '0'
  if (value > 1000) return `${(value / 1000).toFixed(1)}k`
  return String(value)
}

function basenameFromPath(path: string) {
  const normalized = path.trim().replace(/[\\/]+$/, '')
  const parts = normalized.split(/[\\/]/).filter(Boolean)
  return parts[parts.length - 1] || '新项目'
}

function projectDepth(project: Project, projects: Project[]) {
  const bySlug = new Map(projects.map((item) => [item.slug, item]))
  const seen = new Set<string>([project.slug])
  let depth = 0
  let parentSlug = project.parent_slug || null
  while (parentSlug && depth < 12 && !seen.has(parentSlug)) {
    seen.add(parentSlug)
    depth += 1
    parentSlug = bySlug.get(parentSlug)?.parent_slug || null
  }
  return depth
}

function ToolMessage({ item }: { item: ToolConversationItem }) {
  const args = Object.keys(item.args).length ? JSON.stringify(item.args, null, 2) : ''
  const hasDetails = Boolean(args || item.result)

  return (
    <article className="message tool">
      <div className={`tool-card ${item.status}`}>
        <div className="tool-card-header">
          <span className="tool-card-dot" />
          <span className="tool-card-name">{item.toolName}</span>
          <span className="tool-card-status">
            {item.status === 'running'
              ? '运行中'
              : item.status === 'error'
                ? '失败'
                : item.status === 'cancelled'
                  ? '已取消'
                  : '完成'}
          </span>
        </div>
        {hasDetails && (
          <details className="tool-card-details">
            <summary>{item.status === 'running' ? '查看参数' : '查看详情'}</summary>
            {args && <pre><span className="tool-card-detail-label">参数</span>{'\n'}{args}</pre>}
            {item.result && <pre><span className="tool-card-detail-label">结果</span>{'\n'}{item.result}</pre>}
          </details>
        )}
        {item.changedPaths.length > 0 && (
          <div className="tool-card-changed">
            已修改：{item.changedPaths.join(', ')}
          </div>
        )}
      </div>
    </article>
  )
}

function SummaryMessage({ message }: { message: Message }) {
  const seq = typeof message.meta.compaction_seq === 'number' ? message.meta.compaction_seq : '?'
  const summarized = typeof message.meta.summarized_message_count === 'number' ? message.meta.summarized_message_count : 0
  const content = message.content.startsWith(SUMMARY_PREFIX)
    ? message.content.slice(SUMMARY_PREFIX.length)
    : message.content

  return (
    <article className="message summary">
      <details className="summary-card">
        <summary>
          <span>上下文摘要 #{seq}</span>
          <span>{summarized} 条旧消息已压缩</span>
        </summary>
        <div className="summary-card-body">
          <MarkdownRenderer>{content}</MarkdownRenderer>
        </div>
      </details>
    </article>
  )
}

export default function App() {
  const [activePanel, setActivePanel] = useState<ActivePanel>('project')
  const [projects, setProjects] = useState<Project[]>([])
  const [activeSlug, setActiveSlug] = useState<string | null>(null)
  const [sessions, setSessions] = useState<Session[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [messages, setMessages] = useState<Message[]>([])
  const [entries, setEntries] = useState<FileEntry[]>([])
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(() => new Set())
  const [selectedFile, setSelectedFile] = useState<FileEntry | null>(null)
  const [fileContent, setFileContent] = useState<FileContent | null>(null)
  const [fileDraft, setFileDraft] = useState('')
  const [editing, setEditing] = useState(false)
  const [memoryDraft, setMemoryDraft] = useState('')
  const [showCreate, setShowCreate] = useState(false)
  const [showMemory, setShowMemory] = useState(false)
  const [context, setContext] = useState<ContextUsage | null>(null)
  const [input, setInput] = useState('')
  const [status, setStatus] = useState('准备就绪')
  const [error, setError] = useState('')
  const [tokenInput, setTokenInput] = useState(getToken())
  const [settings, setSettings] = useState<AppSettings | null>(null)
  const [settingsDraft, setSettingsDraft] = useState({
    model_base_url: '',
    model_name: '',
    model_api_key: '',
    context_budget_tokens: '700000',
    request_timeout_seconds: '120'
  })
  const [settingsSaving, setSettingsSaving] = useState(false)
  const [clearApiKey, setClearApiKey] = useState(false)
  const [rightWidth, setRightWidth] = useState(() => Number(localStorage.getItem('workmode-file-width') || '460'))
  const [newProject, setNewProject] = useState({ name: '', root_path: '', description: '' })
  const [streaming, setStreaming] = useState(false)
  const [compacting, setCompacting] = useState(false)
  const [pickingFolder, setPickingFolder] = useState(false)
  const [installingTutorial, setInstallingTutorial] = useState(false)
  const [resettingTutorial, setResettingTutorial] = useState(false)
  const [editingSessionId, setEditingSessionId] = useState<string | null>(null)
  const [editingSessionTitle, setEditingSessionTitle] = useState('')
  const streamAbortRef = useRef<AbortController | null>(null)
  const stopRequestedRef = useRef(false)
  const messagesViewportRef = useRef<HTMLElement | null>(null)
  const followingLatestRef = useRef(true)
  const [showBackToLatest, setShowBackToLatest] = useState(false)
  const [desktopInfo] = useState(() => getDesktopInfo())
  const [desktopUpdateStatus, setDesktopUpdateStatus] = useState('')
  const [desktopUpdateVersion, setDesktopUpdateVersion] = useState<string | null>(null)
  const [desktopUpdating, setDesktopUpdating] = useState(false)
  const [desktopUpdateProgress, setDesktopUpdateProgress] = useState(0)
  const [onboardingProgress, setOnboardingProgress] = useState(() => parseProgress(localStorage.getItem(ONBOARDING_STORAGE_KEY)))
  const [modelTesting, setModelTesting] = useState(false)
  const [modelTestStatus, setModelTestStatus] = useState('')
  const [modelTestOk, setModelTestOk] = useState(false)
  const [guideAfterProjectCreate, setGuideAfterProjectCreate] = useState(false)
  const [tutorialChecklistCollapsed, setTutorialChecklistCollapsed] = useState(false)
  const [achievementToast, setAchievementToast] = useState<AchievementDefinition | null>(null)
  const [showContextDetails, setShowContextDetails] = useState(false)
  const announcedAchievementsRef = useRef(new Set(Object.keys(onboardingProgress.achievements)))

  const activeProject = useMemo(
    () => projects.find((item) => item.slug === activeSlug) || null,
    [projects, activeSlug]
  )
  const conversationItems = useMemo(
    () => buildConversationItems(messages, streaming ? 'running' : 'cancelled'),
    [messages, streaming]
  )
  const visibleEntries = useMemo(
    () => visibleFileEntries(entries, expandedDirs),
    [entries, expandedDirs]
  )

  const contextTotal = context?.total_tokens_estimate || context?.estimated_prompt_tokens || context?.prompt_tokens_estimate || 0
  const contextBudget = context?.budget_tokens || 0
  const contextPct = contextBudget ? Math.min(100, (Number(contextTotal) / contextBudget) * 100) : 0
  const historyIncluded = typeof context?.history_messages_included === 'number' ? context.history_messages_included : undefined
  const historyTotal = typeof context?.history_messages_total === 'number' ? context.history_messages_total : undefined
  const historyDropped = typeof context?.history_messages_dropped === 'number' ? context.history_messages_dropped : undefined

  function recordProductEvent(event: ProductEvent) {
    setOnboardingProgress((previous) => {
      const result = applyProductEvent(previous, event)
      return result.progress
    })
  }

  function setOnboardingStage(stage: typeof onboardingProgress.stage, tourStep = onboardingProgress.tourStep) {
    setOnboardingProgress((previous) => ({ ...previous, stage, tourStep }))
  }

  function replayOnboarding() {
    setActivePanel('project')
    setModelTestStatus('')
    setModelTestOk(false)
    setOnboardingProgress((previous) => ({ ...previous, stage: 'welcome', tourStep: 0 }))
  }

  useEffect(() => {
    localStorage.setItem(ONBOARDING_STORAGE_KEY, JSON.stringify(onboardingProgress))
  }, [onboardingProgress])

  useEffect(() => {
    if (!achievementToast) return
    const timer = window.setTimeout(() => setAchievementToast(null), 4200)
    return () => window.clearTimeout(timer)
  }, [achievementToast])

  useEffect(() => {
    const newlyUnlocked = ACHIEVEMENTS.find((achievement) => (
      onboardingProgress.achievements[achievement.id]
      && !announcedAchievementsRef.current.has(achievement.id)
    ))
    if (!newlyUnlocked) return
    announcedAchievementsRef.current.add(newlyUnlocked.id)
    setAchievementToast(newlyUnlocked)
  }, [onboardingProgress.achievements])

  useEffect(() => {
    if (!activeProject?.is_tutorial || !tutorialComplete(onboardingProgress)) return
    if (onboardingProgress.achievements.tutorial_graduate) return
    setOnboardingProgress((previous) => {
      const result = applyProductEvent(previous, 'tutorial_completed')
      return { ...result.progress, stage: 'complete' }
    })
  }, [activeProject?.is_tutorial, onboardingProgress])

  async function refreshProjects() {
    const payload = await api.projects()
    setProjects(payload.projects)
    setActiveSlug(payload.active_slug || payload.projects[0]?.slug || null)
    return payload
  }

  async function loadProject(slug: string) {
    const [sessionPayload, treePayload, memoryPayload] = await Promise.all([
      api.sessions(slug),
      api.tree(slug),
      api.memory(slug)
    ])
    setSessions(sessionPayload.sessions)
    setEntries(treePayload.entries)
    setExpandedDirs(directoryPaths(treePayload.entries))
    setMemoryDraft(memoryPayload.project)
    if (sessionPayload.sessions[0]) {
      setSessionId(sessionPayload.sessions[0].id)
    } else {
      const created = await api.createSession(slug)
      setSessions([created.session])
      setSessionId(created.session.id)
    }
  }

  async function loadMessages(id: string) {
    const [messagePayload, contextPayload] = await Promise.all([api.messages(id), api.context(id)])
    setMessages(messagePayload.messages)
    setContext(contextPayload.context)
  }

  function scrollToLatest(behavior: ScrollBehavior = 'auto') {
    const viewport = messagesViewportRef.current
    if (!viewport) return
    followingLatestRef.current = true
    setShowBackToLatest(false)
    viewport.scrollTo({ top: viewport.scrollHeight, behavior })
  }

  function handleMessagesScroll() {
    const viewport = messagesViewportRef.current
    if (!viewport) return
    const nearBottom = isNearBottom(viewport)
    followingLatestRef.current = nearBottom
    setShowBackToLatest(!nearBottom)
  }

  useEffect(() => {
    refreshProjects().catch((exc) => setError(String(exc)))
    loadSettings().catch((exc) => setError(String(exc)))
  }, [])

  useEffect(() => {
    if (!desktopInfo) return
    checkForDesktopUpdate()
      .then((update) => {
        if (update) {
          setDesktopUpdateVersion(update.version)
          setDesktopUpdateStatus(`发现新版本 ${update.version}`)
        }
      })
      .catch(() => {
        // Automatic checks stay quiet. Manual checks show actionable errors.
      })
  }, [desktopInfo])

  async function loadSettings() {
    const payload = await api.settings()
    setSettings(payload.settings)
    setSettingsDraft({
      model_base_url: payload.settings.model_base_url,
      model_name: payload.settings.model_name,
      model_api_key: '',
      context_budget_tokens: String(payload.settings.context_budget_tokens),
      request_timeout_seconds: String(payload.settings.request_timeout_seconds)
    })
  }

  useEffect(() => {
    if (!activeSlug) return
    setStatus('加载项目中…')
    loadProject(activeSlug)
      .then(() => setStatus('项目已加载'))
      .catch((exc) => setError(String(exc)))
  }, [activeSlug])

  useEffect(() => {
    followingLatestRef.current = true
    setShowBackToLatest(false)
  }, [sessionId])

  useEffect(() => {
    if (!followingLatestRef.current) return
    const frame = window.requestAnimationFrame(() => scrollToLatest())
    return () => window.cancelAnimationFrame(frame)
  }, [messages])

  useEffect(() => {
    if (!sessionId) {
      setMessages([])
      setContext(null)
      return
    }
    loadMessages(sessionId).catch((exc) => setError(String(exc)))
  }, [sessionId])

  function applyToken() {
    setToken(tokenInput)
    setStatus(tokenInput ? '本地访问令牌已保存' : '本地访问令牌已清空')
    refreshProjects().catch((exc) => setError(String(exc)))
  }

  async function saveModelSettings() {
    setSettingsSaving(true)
    setError('')
    try {
      const payload = await api.saveModelSettings({
        model_base_url: settingsDraft.model_base_url.trim(),
        model_name: settingsDraft.model_name.trim(),
        model_api_key: settingsDraft.model_api_key.trim() || undefined,
        clear_api_key: clearApiKey,
        context_budget_tokens: Number(settingsDraft.context_budget_tokens),
        request_timeout_seconds: Number(settingsDraft.request_timeout_seconds)
      })
      setSettings(payload.settings)
      setSettingsDraft((prev) => ({ ...prev, model_api_key: '' }))
      setClearApiKey(false)
      setStatus('模型设置已保存，下一轮请求立即生效')
      if (sessionId) {
        const contextPayload = await api.context(sessionId)
        setContext(contextPayload.context)
      }
    } catch (exc) {
      setError(String(exc))
    } finally {
      setSettingsSaving(false)
    }
  }

  async function testModelConnection(saveAfterSuccess: boolean) {
    if (modelTesting) return
    setModelTesting(true)
    setModelTestStatus('正在连接模型服务…')
    setModelTestOk(false)
    setError('')
    try {
      const tested = await api.testModelConnection({
        model_base_url: settingsDraft.model_base_url.trim(),
        model_name: settingsDraft.model_name.trim(),
        model_api_key: settingsDraft.model_api_key.trim() || undefined
      })
      if (saveAfterSuccess) {
        const saved = await api.saveModelSettings({
          model_base_url: settingsDraft.model_base_url.trim(),
          model_name: settingsDraft.model_name.trim(),
          model_api_key: settingsDraft.model_api_key.trim() || undefined,
          context_budget_tokens: Number(settingsDraft.context_budget_tokens),
          request_timeout_seconds: Number(settingsDraft.request_timeout_seconds)
        })
        setSettings(saved.settings)
        setSettingsDraft((previous) => ({ ...previous, model_api_key: '' }))
      }
      setModelTestOk(true)
      setModelTestStatus(`✓ ${tested.message} · ${tested.model} · ${tested.latency_ms} ms`)
      setStatus('模型连接测试成功')
      recordProductEvent('model_connected')
    } catch (exc) {
      const message = exc instanceof Error ? exc.message : String(exc)
      setModelTestStatus(`连接失败：${message}`)
      setModelTestOk(false)
    } finally {
      setModelTesting(false)
    }
  }

  async function checkDesktopUpdate() {
    setDesktopUpdateStatus('正在检查更新…')
    setError('')
    try {
      const update = await checkForDesktopUpdate()
      if (update) {
        setDesktopUpdateVersion(update.version)
        setDesktopUpdateStatus(`发现新版本 ${update.version}`)
      } else {
        setDesktopUpdateVersion(null)
        setDesktopUpdateStatus('当前已经是最新版本')
      }
    } catch (exc) {
      setDesktopUpdateStatus('检查更新失败')
      setError(String(exc))
    }
  }

  async function installUpdate() {
    setDesktopUpdating(true)
    setDesktopUpdateStatus(`正在下载 ${desktopUpdateVersion || '新版本'}…`)
    setError('')
    try {
      await installDesktopUpdate((downloaded, total) => {
        setDesktopUpdateProgress(total ? Math.min(100, downloaded / total * 100) : 0)
      })
    } catch (exc) {
      setError(String(exc))
      setDesktopUpdateStatus('更新安装失败，当前版本未被替换')
      setDesktopUpdating(false)
    }
  }

  async function migrateLegacyPortable() {
    if (!window.confirm('导入旧版便携包的项目、会话、工作记忆和 API 配置？\n\n旧版文件夹不会被修改，导入成功后应用会自动重启。')) return
    setError('')
    try {
      const result = await chooseAndMigrateLegacyPortable()
      if (!result) setDesktopUpdateStatus('已取消旧版数据导入')
    } catch (exc) {
      setError(String(exc))
    }
  }

  async function pickDirectory() {
    if (pickingFolder) return
    setPickingFolder(true)
    setError('')
    try {
      const picked = await api.pickDirectory()
      if (picked.path) {
        setNewProject((prev) => ({
          ...prev,
          root_path: picked.path || '',
          name: prev.name || basenameFromPath(picked.path || '')
        }))
      }
    } catch (exc) {
      setError(`选目录失败：${exc instanceof Error ? exc.message : String(exc)}。也可以手动输入绝对路径。`)
    } finally {
      setPickingFolder(false)
    }
  }

  async function createProject() {
    setError('')
    const payload = {
      ...newProject,
      name: newProject.name.trim() || basenameFromPath(newProject.root_path)
    }
    const created = await api.createProject(payload)
    setNewProject({ name: '', root_path: '', description: '' })
    setShowCreate(false)
    await refreshProjects()
    setActiveSlug(created.project.slug)
    setSessionId(created.session.id)
    recordProductEvent('project_created')
    if (guideAfterProjectCreate) {
      setGuideAfterProjectCreate(false)
      setOnboardingProgress((previous) => ({ ...previous, stage: 'tour', tourStep: 0 }))
    }
  }

  async function createTutorialProject(startGuide = false) {
    if (pickingFolder || installingTutorial) return
    setPickingFolder(true)
    setInstallingTutorial(true)
    setError('')
    try {
      const picked = await api.pickDirectory()
      if (!picked.path) {
        setStatus('已取消创建教程项目')
        return
      }
      const created = await api.installTutorialProject(picked.path)
      await refreshProjects()
      setActiveSlug(created.project.slug)
      setSessionId(created.session.id)
      setSelectedFile(null)
      setFileContent(null)
      setStatus('教程项目已创建；发送“开始教程”即可体验')
      recordProductEvent('project_created')
      setOnboardingProgress((previous) => ({
        ...resetTutorialTasks(previous),
        stage: startGuide ? 'tour' : previous.stage,
        tourStep: startGuide ? 0 : previous.tourStep
      }))
    } catch (exc) {
      setError(String(exc))
    } finally {
      setPickingFolder(false)
      setInstallingTutorial(false)
    }
  }

  async function resetTutorialProject() {
    if (!activeProject?.is_tutorial || streaming || resettingTutorial) return
    const confirmed = window.confirm(
      '重置官方教程项目？\n\n' +
      '将恢复安装包内的初始教程文件，清空该项目的工作记忆和当前计划，并把旧会话移入本地归档。\n' +
      '重置前会自动完整备份，其他项目不受影响。'
    )
    if (!confirmed) return
    setResettingTutorial(true)
    setError('')
    try {
      const result = await api.resetTutorialProject(activeProject.slug)
      setSelectedFile(null)
      setFileContent(null)
      setEntries([])
      await refreshProjects()
      setActiveSlug(result.project.slug)
      await loadProject(result.project.slug)
      setSessionId(result.session.id)
      setStatus(`教程已重置；恢复前备份：${result.backup_path}`)
      setOnboardingProgress((previous) => resetTutorialTasks(previous))
    } catch (exc) {
      setError(String(exc))
    } finally {
      setResettingTutorial(false)
    }
  }

  async function switchProject(slug: string) {
    if (!slug || slug === activeSlug) return
    setError('')
    await api.setActive(slug)
    setActiveSlug(slug)
    setSelectedFile(null)
    setFileContent(null)
  }

  async function newSession() {
    if (!activeSlug) return
    const created = await api.createSession(activeSlug)
    setSessions((prev) => [created.session, ...prev])
    setSessionId(created.session.id)
  }

  function startRenamingSession(session: Session) {
    setEditingSessionId(session.id)
    setEditingSessionTitle(session.title)
  }

  async function saveSessionTitle(session: Session) {
    const title = editingSessionTitle.trim()
    if (!title) {
      setEditingSessionId(null)
      return
    }
    setError('')
    try {
      const updated = await api.updateSession(session.id, title)
      setSessions((prev) => prev.map((item) => item.id === session.id ? updated.session : item))
      setEditingSessionId(null)
      setStatus('会话名称已修改')
    } catch (exc) {
      setError(String(exc))
    }
  }

  async function deleteSession(session: Session) {
    if (streaming && session.id === sessionId) return
    if (!window.confirm(`删除会话“${session.title}”？\n\n历史记录会保留在本地归档中，不会立即物理删除。`)) return
    setError('')
    try {
      await api.deleteSession(session.id)
      const remaining = sessions.filter((item) => item.id !== session.id)
      setSessions(remaining)
      if (sessionId === session.id) {
        setSessionId(remaining[0]?.id || null)
      }
      setStatus('会话已移入本地归档')
    } catch (exc) {
      setError(String(exc))
    }
  }

  async function deleteActiveProject() {
    if (!activeProject || streaming) return
    const confirmed = window.confirm(
      `从 Workmode Public 中移除项目“${activeProject.name}”？\n\n` +
      `不会删除硬盘中的文件：\n${activeProject.root_path}\n\n` +
      '该项目的会话和工作记忆会保留在本地归档中。'
    )
    if (!confirmed) return
    setError('')
    try {
      await api.deleteProject(activeProject.slug)
      setSelectedFile(null)
      setFileContent(null)
      setEntries([])
      setExpandedDirs(new Set())
      setSessions([])
      setSessionId(null)
      const payload = await refreshProjects()
      setStatus(payload.projects.length ? '项目已从列表移除，本地文件未删除' : '项目已移除，本地文件未删除')
    } catch (exc) {
      setError(String(exc))
    }
  }

  async function openFile(entry: FileEntry) {
    if (entry.kind === 'dir') {
      setExpandedDirs((previous) => {
        const next = new Set(previous)
        if (next.has(entry.path)) next.delete(entry.path)
        else next.add(entry.path)
        return next
      })
      return
    }
    setSelectedFile(entry)
    setFileContent(null)
    setFileDraft('')
    setEditing(false)
    if (!activeSlug) return
    if (isPdf(entry.path)) recordProductEvent('pdf_opened')
    if (entry.preview === 'text') {
      const content = await api.readFile(activeSlug, entry.path)
      setFileContent(content)
      setFileDraft(content.content)
    }
  }

  async function saveFile() {
    if (!activeSlug || !selectedFile || !fileContent) return
    const saved = await api.saveFile(activeSlug, selectedFile.path, fileDraft, fileContent.version)
    setFileContent(saved)
    setFileDraft(saved.content)
    setEditing(false)
    setStatus('Markdown 已保存')
    recordProductEvent('markdown_saved')
  }

  async function saveMemory() {
    if (!activeSlug) return
    await api.saveMemory(activeSlug, memoryDraft)
    setStatus('项目工作记忆已保存；@文件会在下一轮聊天时重新注入')
    if (sessionId) {
      const contextPayload = await api.context(sessionId)
      setContext(contextPayload.context)
    }
  }

  async function compactContext() {
    if (!sessionId || compacting || streaming) return
    setCompacting(true)
    setError('')
    try {
      const result = await api.compact(sessionId, 6)
      setContext(result.context)
      await loadMessages(sessionId)
      setStatus(`上下文已压缩：摘要 #${result.compaction.compaction_seq}，压缩 ${result.compaction.summarized_count} 条`)
      recordProductEvent('context_compacted')
    } catch (exc) {
      setError(String(exc))
    } finally {
      setCompacting(false)
    }
  }

  async function send() {
    if (!sessionId || !input.trim() || streaming) return
    const activeSessionId = sessionId
    const content = input.trim()
    const controller = new AbortController()
    streamAbortRef.current = controller
    stopRequestedRef.current = false
    followingLatestRef.current = true
    setShowBackToLatest(false)
    setInput('')
    setStreaming(true)
    setError('')
    recordProductEvent('message_sent')
    let placeholderId = ''
    let assistantText = ''
    let segmentIndex = 0
    let projectFilesChanged = false
    try {
      await streamChat(activeSessionId, content, (event) => {
        if (event.type === 'user_message') {
          setMessages((prev) => [...prev, event.message as Message])
        }
        if (event.type === 'context_usage') {
          setContext(event.context as ContextUsage)
        }
        if (event.type === 'text_delta') {
          assistantText += String(event.content || '')
          if (!placeholderId) {
            placeholderId = `stream-${Date.now()}-${segmentIndex++}`
          }
          setMessages((prev) => {
            const existing = prev.find((item) => item.id === placeholderId)
            if (existing) {
              return prev.map((item) => item.id === placeholderId ? { ...item, content: assistantText } : item)
            }
            return [
              ...prev,
              { id: placeholderId, role: 'assistant', content: assistantText, ts: new Date().toISOString(), meta: {} }
            ]
          })
        }
        if (event.type === 'tool_call_start' || event.type === 'tool_result') {
          const message = event.message as Message | undefined
          if (message) {
            setMessages((prev) => [...prev, message])
          }
          placeholderId = ''
          assistantText = ''
        }
        if (event.type === 'tool_result' && event.ok !== false) {
          const toolName = String(event.name || '')
          if (toolName === 'web_search' || toolName === 'web_fetch') recordProductEvent('web_researched')
          if (toolName === 'project_python' || toolName === 'project_python_file' || toolName === 'project_bash') recordProductEvent('analysis_run')
        }
        if (event.type === 'tool_result') {
          const changed = Array.isArray(event.changed_paths) ? event.changed_paths : []
          if (changed.length > 0) projectFilesChanged = true
        }
        if (event.type === 'loop_continue') {
          setStatus(`工具调用完成，继续生成第 ${event.round || '?'} 轮`)
        }
        if (event.type === 'error') {
          setError(String(event.message || '聊天失败'))
        }
        if (event.type === 'cancelled') {
          stopRequestedRef.current = true
          setStatus('本轮生成已停止')
        }
      }, controller.signal)
      if (projectFilesChanged && activeSlug) {
        const treePayload = await api.tree(activeSlug)
        setEntries(treePayload.entries)
        setExpandedDirs((previous) => {
          const nextDirectories = directoryPaths(treePayload.entries)
          return new Set([...previous].filter((path) => nextDirectories.has(path)))
        })
        if (selectedFile?.preview === 'text') {
          try {
            const contentPayload = await api.readFile(activeSlug, selectedFile.path)
            setFileContent(contentPayload)
            setFileDraft(contentPayload.content)
          } catch {
            setFileContent(null)
          }
        }
      }
      setStatus(stopRequestedRef.current ? '本轮生成已停止' : '回复完成')
    } catch (exc) {
      if (stopRequestedRef.current || controller.signal.aborted) {
        setStatus('本轮生成已停止')
      } else {
        setError(String(exc))
      }
    } finally {
      if (streamAbortRef.current === controller) streamAbortRef.current = null
      setStreaming(false)
      try {
        await loadMessages(activeSessionId)
      } catch (exc) {
        if (!stopRequestedRef.current) setError(String(exc))
      }
    }
  }

  async function stopGeneration() {
    if (!sessionId || !streaming) return
    stopRequestedRef.current = true
    setStatus('正在停止本轮生成…')
    try {
      await api.stopChat(sessionId)
    } catch (exc) {
      setError(String(exc))
    } finally {
      streamAbortRef.current?.abort()
    }
  }

  function chooseOwnProjectFromOnboarding() {
    setActivePanel('project')
    setShowCreate(true)
    setGuideAfterProjectCreate(true)
    setOnboardingStage('complete', 0)
    setStatus('请在左侧选择自己的项目文件夹；创建后会继续界面指引')
  }

  function handleTutorialTask(taskId: TutorialTaskId, prompt?: string) {
    setActivePanel('project')
    if (prompt) {
      setInput(prompt)
      setStatus('示例指令已填入输入框；检查后按 Ctrl+Enter 发送')
      window.setTimeout(() => document.querySelector<HTMLTextAreaElement>('[data-guide="composer"] textarea')?.focus(), 0)
      return
    }
    if (taskId === 'view_context') {
      setShowContextDetails(true)
      recordProductEvent('context_viewed')
      setStatus('已打开上下文明细')
      return
    }
    if (taskId === 'open_pdf') setStatus('请在左侧文件树的 papers/ 中点击 PDF 文件')
    if (taskId === 'edit_markdown') setStatus('请从左侧打开一份 Markdown，在右侧点“编辑”并保存')
  }

  function openProjectAfterTutorial() {
    setTutorialChecklistCollapsed(true)
    setActivePanel('project')
    setShowCreate(true)
    setStatus('选择一个正式工作文件夹，开始你的项目')
  }

  function startResize(event: React.MouseEvent) {
    event.preventDefault()
    const startX = event.clientX
    const startWidth = rightWidth
    function move(moveEvent: MouseEvent) {
      const next = Math.min(820, Math.max(340, startWidth - (moveEvent.clientX - startX)))
      setRightWidth(next)
      localStorage.setItem('workmode-file-width', String(next))
    }
    function up() {
      window.removeEventListener('mousemove', move)
      window.removeEventListener('mouseup', up)
    }
    window.addEventListener('mousemove', move)
    window.addEventListener('mouseup', up)
  }

  return (
    <div
      className="ide-shell"
      style={{
        gridTemplateColumns: `48px 280px minmax(420px, 1fr) 6px ${rightWidth}px`,
        gridTemplateRows: '1fr 24px'
      }}
    >
      <nav className="activity-bar" aria-label="主活动栏">
        <div className="activity-bar-top">
          <button
            type="button"
            className={`activity-btn ${activePanel === 'project' ? 'active' : ''}`}
            title="项目"
            onClick={() => setActivePanel('project')}
          >
            <span className="activity-icon">▣</span>
          </button>
        </div>
        <div className="activity-bar-bottom">
          <button
            type="button"
            className={`activity-btn ${activePanel === 'settings' ? 'active' : ''}`}
            title="设置"
            onClick={() => setActivePanel('settings')}
          >
            <span className="activity-icon">⚙</span>
          </button>
        </div>
      </nav>

      <aside className="side-panel">
        <header className="side-panel-header">
          <span className="side-panel-title">{activePanel === 'project' ? '项目' : '设置'}</span>
        </header>

        {activePanel === 'project' ? (
          <div className="project-panel">
            <section className="project-switcher" data-guide="projects">
              <div className="project-switcher-row">
                <label className="project-switcher-label">项目</label>
                <span className="project-switcher-spacer" />
                <button
                  type="button"
                  className="project-switcher-icon-btn"
                  onClick={() => setShowCreate((value) => !value)}
                  title="打开文件夹"
                >
                  +
                </button>
                <button
                  type="button"
                  className="project-switcher-icon-btn"
                  onClick={() => activeSlug && loadProject(activeSlug)}
                  disabled={!activeSlug}
                  title="刷新"
                >
                  ↻
                </button>
                <button
                  type="button"
                  className="project-switcher-icon-btn danger"
                  onClick={deleteActiveProject}
                  disabled={!activeProject || streaming}
                  title="移除当前项目（不删除本地文件）"
                >
                  ×
                </button>
              </div>
              <div className="project-tree-list" role="tree" aria-label="项目列表">
                {projects.map((project) => {
                  const depth = projectDepth(project, projects)
                  return (
                    <button
                      type="button"
                      role="treeitem"
                      aria-selected={project.slug === activeSlug}
                      key={project.slug}
                      className={project.slug === activeSlug ? 'project-tree-row active' : 'project-tree-row'}
                      style={{ paddingLeft: 8 + depth * 16 }}
                      onClick={() => switchProject(project.slug)}
                      disabled={streaming}
                      title={project.root_path}
                    >
                      <span className="project-tree-branch">{depth ? '└' : '▾'}</span>
                      <span className="project-tree-name">{project.name}</span>
                    </button>
                  )
                })}
                {projects.length === 0 && <div className="project-tree-empty">点 + 打开一个文件夹</div>}
              </div>
              <div className="tutorial-project-actions">
                <button
                  type="button"
                  className="project-create-cancel"
                  onClick={() => createTutorialProject()}
                  disabled={pickingFolder || installingTutorial || streaming}
                >
                  {installingTutorial ? '创建教程中…' : '创建教程项目'}
                </button>
                {activeProject?.is_tutorial && (
                  <button
                    type="button"
                    className="project-create-cancel tutorial-reset-btn"
                    onClick={resetTutorialProject}
                    disabled={resettingTutorial || streaming}
                  >
                    {resettingTutorial ? '重置中…' : '重置教程'}
                  </button>
                )}
              </div>
              {activeProject && !showCreate && (
                <div className="project-switcher-path" title={activeProject.root_path}>
                  {activeProject.root_path}
                </div>
              )}
              {showCreate && (
                <div className="project-create-form">
                  <div className="project-create-path-row">
                    <input
                      className="project-create-input"
                      value={newProject.root_path}
                      onChange={(event) => setNewProject({ ...newProject, root_path: event.target.value })}
                      placeholder="绝对路径（或点 📁）"
                    />
                    <button
                      type="button"
                      className="project-create-browse"
                      onClick={pickDirectory}
                      disabled={pickingFolder}
                      title="选择文件夹"
                    >
                      {pickingFolder ? '…' : '📁'}
                    </button>
                  </div>
                  <input
                    className="project-create-input"
                    value={newProject.name}
                    onChange={(event) => setNewProject({ ...newProject, name: event.target.value })}
                    placeholder="显示名（可选）"
                  />
                  <textarea
                    className="project-create-input project-create-textarea"
                    value={newProject.description}
                    onChange={(event) => setNewProject({ ...newProject, description: event.target.value })}
                    placeholder="项目描述（可选）"
                  />
                  <div className="project-create-actions">
                    <button
                      type="button"
                      className="project-create-submit"
                      onClick={createProject}
                      disabled={!newProject.root_path.trim()}
                    >
                      打开
                    </button>
                    <button
                      type="button"
                      className="project-create-cancel"
                      onClick={() => setShowCreate(false)}
                    >
                      取消
                    </button>
                  </div>
                </div>
              )}
              {error && <div className="project-switcher-error">{error}</div>}
            </section>

            <section className="project-section" data-guide="files">
              <div className="project-section-title">文件</div>
              <div className="project-section-body project-section-body-tree">
                {activeSlug ? (
                  <div className="file-explorer-tree">
                    {visibleEntries.map((entry) => (
                      <button
                        type="button"
                        key={entry.path}
                        className={selectedFile?.path === entry.path ? 'tree-node selected' : 'tree-node'}
                        style={{ paddingLeft: 6 + fileDepth(entry.path) * 12 }}
                        onClick={() => openFile(entry).catch((exc) => setError(String(exc)))}
                        title={entry.path}
                        aria-expanded={entry.kind === 'dir' ? expandedDirs.has(entry.path) : undefined}
                      >
                        <span className="tree-node-icon">
                          {entry.kind === 'dir' ? (expandedDirs.has(entry.path) ? '▾' : '▸') : entry.preview === 'media' ? '◇' : entry.preview === 'text' ? '·' : '×'}
                        </span>
                        <span className="tree-node-name">{entry.name}</span>
                        {entry.kind === 'file' && <span className="tree-node-size">{entry.preview}</span>}
                      </button>
                    ))}
                    {entries.length === 0 && <div className="file-explorer-empty">暂无可显示文件</div>}
                  </div>
                ) : (
                  <div className="file-explorer-empty">先打开一个文件夹</div>
                )}
              </div>
            </section>

            <section className="project-section project-section-sessions">
              <div className="project-section-title">会话</div>
              <div className="project-section-body">
                <div className="sessions-toolbar">
                  <button type="button" className="sessions-new-btn" onClick={newSession} disabled={!activeSlug}>+ 新对话</button>
                </div>
                <div className="sessions-list">
                  {sessions.map((session) => (
                    <div
                      key={session.id}
                      className={session.id === sessionId ? 'session-row active' : 'session-row'}
                    >
                      {editingSessionId === session.id ? (
                        <input
                          className="session-title-input"
                          value={editingSessionTitle}
                          maxLength={80}
                          autoFocus
                          onChange={(event) => setEditingSessionTitle(event.target.value)}
                          onBlur={() => setEditingSessionId(null)}
                          onKeyDown={(event) => {
                            if (event.key === 'Enter') {
                              event.preventDefault()
                              saveSessionTitle(session)
                            }
                            if (event.key === 'Escape') {
                              event.preventDefault()
                              setEditingSessionId(null)
                            }
                          }}
                        />
                      ) : (
                        <button
                          type="button"
                          className="session-row-main"
                          onClick={() => setSessionId(session.id)}
                          onDoubleClick={() => startRenamingSession(session)}
                          title="双击重命名"
                        >
                          <span className="session-row-title">{session.title}</span>
                          <span className="session-row-meta">{session.message_count} 条 · {session.id.slice(0, 8)}</span>
                        </button>
                      )}
                      <span className="session-row-actions">
                        <button
                          type="button"
                          className="session-action-btn"
                          onClick={() => startRenamingSession(session)}
                          title="重命名"
                        >
                          ✎
                        </button>
                        <button
                          type="button"
                          className="session-action-btn danger"
                          onClick={() => deleteSession(session)}
                          disabled={streaming && session.id === sessionId}
                          title="删除会话"
                        >
                          ×
                        </button>
                      </span>
                    </div>
                  ))}
                  {sessions.length === 0 && <div className="sessions-empty">暂无会话</div>}
                </div>
              </div>
            </section>
          </div>
        ) : (
          <div className="settings-panel">
            {desktopInfo && (
              <section className="settings-section desktop-settings-section">
                <div className="settings-label">桌面应用</div>
                <div className="desktop-version-row">
                  <span>当前版本</span>
                  <strong>{desktopInfo.version}</strong>
                </div>
                <div className="settings-hint">用户数据：{desktopInfo.dataDir}</div>
                <div className="desktop-update-actions">
                  <button
                    type="button"
                    className="project-create-submit"
                    onClick={checkDesktopUpdate}
                    disabled={desktopUpdating}
                  >
                    检查更新
                  </button>
                  {desktopUpdateVersion && (
                    <button
                      type="button"
                      className="project-create-submit"
                      onClick={installUpdate}
                      disabled={desktopUpdating}
                    >
                      {desktopUpdating ? '正在更新…' : `安装 ${desktopUpdateVersion}`}
                    </button>
                  )}
                </div>
                {desktopUpdateStatus && <div className="settings-hint">{desktopUpdateStatus}</div>}
                {desktopUpdating && (
                  <div className="desktop-update-progress" aria-label="更新下载进度">
                    <span style={{ width: `${desktopUpdateProgress}%` }} />
                  </div>
                )}
                {desktopInfo.migrationAvailable && (
                  <button
                    type="button"
                    className="project-create-cancel desktop-migrate-btn"
                    onClick={migrateLegacyPortable}
                  >
                    导入旧版便携包数据
                  </button>
                )}
                <div className="settings-hint">关闭应用窗口会同时停止本地后端；最小化后可从托盘重新显示，也可从托盘停止并退出。</div>
              </section>
            )}
            <section className="settings-section">
              <div className="settings-label">模型 API</div>
              <label className="settings-field">
                <span>Base URL</span>
                <input
                  className="project-create-input"
                  value={settingsDraft.model_base_url}
                  onChange={(event) => {
                    setSettingsDraft({ ...settingsDraft, model_base_url: event.target.value })
                    setModelTestOk(false)
                    setModelTestStatus('')
                  }}
                  placeholder="https://api.example.com/v1"
                />
              </label>
              <label className="settings-field">
                <span>Model Name</span>
                <input
                  className="project-create-input"
                  value={settingsDraft.model_name}
                  onChange={(event) => {
                    setSettingsDraft({ ...settingsDraft, model_name: event.target.value })
                    setModelTestOk(false)
                    setModelTestStatus('')
                  }}
                  placeholder="deepseek-v4-pro"
                />
              </label>
              <label className="settings-field">
                <span>API Key</span>
                <input
                  className="project-create-input"
                  type="password"
                  value={settingsDraft.model_api_key}
                  onChange={(event) => {
                    setSettingsDraft({ ...settingsDraft, model_api_key: event.target.value })
                    setModelTestOk(false)
                    setModelTestStatus('')
                  }}
                  placeholder={settings?.model_api_key_set ? '已配置；留空则不修改' : '未配置'}
                  disabled={clearApiKey}
                />
              </label>
              <label className="settings-toggle">
                <input
                  type="checkbox"
                  checked={clearApiKey}
                  onChange={(event) => setClearApiKey(event.target.checked)}
                />
                清空当前 API Key
              </label>
              <div className="settings-grid">
                <label className="settings-field">
                  <span>Context Budget</span>
                  <input
                    className="project-create-input"
                    type="number"
                    min={1000}
                    max={5000000}
                    value={settingsDraft.context_budget_tokens}
                    onChange={(event) => setSettingsDraft({ ...settingsDraft, context_budget_tokens: event.target.value })}
                  />
                </label>
                <label className="settings-field">
                  <span>Timeout 秒</span>
                  <input
                    className="project-create-input"
                    type="number"
                    min={5}
                    max={600}
                    value={settingsDraft.request_timeout_seconds}
                    onChange={(event) => setSettingsDraft({ ...settingsDraft, request_timeout_seconds: event.target.value })}
                  />
                </label>
              </div>
              <div className="settings-hint">
                API Key 不会回显；保存后写入本地 .env，下一轮聊天请求立即生效。
              </div>
              {modelTestStatus && <div className={modelTestOk ? 'settings-test-result success' : 'settings-test-result'}>{modelTestStatus}</div>}
              <div className="settings-button-row">
                <button
                  type="button"
                  className="project-create-cancel"
                  onClick={() => testModelConnection(false)}
                  disabled={modelTesting || !settingsDraft.model_base_url.trim() || !settingsDraft.model_name.trim()}
                >
                  {modelTesting ? '测试中…' : '测试连接'}
                </button>
                <button
                  type="button"
                  className="project-create-submit"
                  onClick={saveModelSettings}
                  disabled={settingsSaving || !settingsDraft.model_base_url.trim() || !settingsDraft.model_name.trim()}
                >
                  {settingsSaving ? '保存中…' : '保存模型设置'}
                </button>
              </div>
            </section>
            <section className="settings-section">
              <div className="settings-label">新手引导与成就</div>
              <p className="settings-hint">引导和成就只保存在本机，不上传，不影响项目文件或对话。</p>
              <div className="settings-button-row">
                <button type="button" className="project-create-submit" onClick={replayOnboarding}>重新播放新手引导</button>
                <button
                  type="button"
                  className="project-create-cancel"
                  onClick={() => setOnboardingProgress((previous) => resetTutorialTasks(previous))}
                >
                  重置教程清单
                </button>
              </div>
              <AchievementPanel progress={onboardingProgress} />
            </section>
            <section className="settings-section">
              <div className="settings-label">连接</div>
              <div className="settings-api">{API_BASE}</div>
              <input
                className="project-create-input"
                value={tokenInput}
                onChange={(event) => setTokenInput(event.target.value)}
                placeholder="X-Workmode-Token（可选）"
              />
              <button type="button" className="project-create-submit" onClick={applyToken}>保存 token</button>
            </section>
            <section className="settings-section">
              <div className="settings-label">项目工作记忆</div>
              <p className="settings-hint">支持独占一行 <code>@相对路径.md</code> 固定注入上下文。</p>
              <textarea
                className="memory-editor"
                value={memoryDraft}
                onChange={(event) => setMemoryDraft(event.target.value)}
                disabled={!activeSlug}
              />
              <button type="button" className="project-create-submit" onClick={saveMemory} disabled={!activeSlug}>保存工作记忆</button>
            </section>
            <label className="settings-toggle">
              <input type="checkbox" checked={showMemory} onChange={(event) => setShowMemory(event.target.checked)} />
              在聊天顶部显示工作记忆编辑区
            </label>
          </div>
        )}
      </aside>

      <main className="ai-panel">
        <header className="ai-panel-header" data-guide="context">
          <div className="ai-panel-header-top">
            <span className="ai-panel-title">AI 助手</span>
            <span className="ai-panel-meta">
              {activeProject ? `${activeProject.name} · ${activeProject.root_path}` : '打开一个项目文件夹开始'}
            </span>
            <button
              type="button"
              className="ai-panel-compact-btn"
              onClick={compactContext}
              disabled={!sessionId || streaming || compacting}
              title="把较早历史压缩成摘要 marker；不会删除原始 JSONL 历史"
            >
              {compacting ? '压缩中…' : '压缩上下文'}
            </button>
            <button type="button" className="ai-panel-compact-btn" onClick={() => setShowMemory((value) => !value)}>
              工作记忆
            </button>
          </div>
          {context && (
            <button
              type="button"
              className={`ai-panel-token-bar ${context.over_budget ? 'over-threshold' : ''}`}
              title={`估算 ${formatTokens(contextTotal)} / ${formatTokens(contextBudget)} tokens`}
              onClick={() => {
                setShowContextDetails((value) => !value)
                recordProductEvent('context_viewed')
              }}
            >
              <div className="ai-panel-token-bar-fill" style={{ width: `${contextPct.toFixed(2)}%` }} />
              <span className="ai-panel-token-bar-label">
                ≈ {formatTokens(contextTotal)} / {formatTokens(contextBudget)} tok · @文件 {context.imported_files?.length || 0}
                {context.project_prompt_file ? ` · 项目提示词 ${formatTokens(context.project_prompt_total_tokens || context.project_prompt_tokens || 0)}` : ''}
                {historyIncluded !== undefined && historyTotal !== undefined ? ` · 历史 ${historyIncluded}/${historyTotal}` : ''}
                {historyDropped ? ` · 省略 ${historyDropped}` : ''}
                {context.has_summary ? ' · 有摘要' : ''}
                {context.import_errors?.length ? ` · 导入警告 ${context.import_errors.length}` : ''}
              </span>
            </button>
          )}
          {context && showContextDetails && (
            <section className="context-detail-popover">
              <div><span>总估算</span><strong>{formatTokens(contextTotal)} tok</strong></div>
              <div><span>预算</span><strong>{formatTokens(contextBudget)} tok</strong></div>
              <div><span>历史</span><strong>{formatTokens(context.history_tokens)} tok</strong></div>
              <div><span>纳入消息</span><strong>{historyIncluded ?? context.history_message_count ?? 0}</strong></div>
              <div><span>固定导入</span><strong>{context.imported_files?.length || 0} 个文件</strong></div>
              <div><span>状态</span><strong>{context.over_budget ? '超出预算' : context.has_summary ? '已有摘要' : '正常'}</strong></div>
            </section>
          )}
        </header>

        {showMemory && (
          <section className="memory-box">
            <div className="memory-help">项目记忆支持独占一行 <code>@相对路径.md</code> 固定注入上下文。</div>
            <textarea value={memoryDraft} onChange={(event) => setMemoryDraft(event.target.value)} />
            <button className="project-create-submit" onClick={saveMemory}>保存工作记忆</button>
          </section>
        )}

        <div className="ai-panel-messages-shell" data-guide="chat">
          <section
            className="ai-panel-messages"
            ref={messagesViewportRef}
            onScroll={handleMessagesScroll}
          >
            {conversationItems.length === 0 ? (
              <div className="empty-hint">{sessionId ? '本会话还没消息' : '新会话 · 输入消息开始对话'}</div>
            ) : (
              conversationItems.map((item) => {
                if (item.kind === 'tool') return <ToolMessage key={item.key} item={item} />
                const message = item.message
                return message.role === 'system' && message.meta?.event === 'context_summary'
                  ? <SummaryMessage key={item.key} message={message} />
                  : (
                    <article key={item.key} className={`message ${message.role}`}>
                      <div className="bubble">
                        {message.role === 'assistant' ? <MarkdownRenderer>{message.content}</MarkdownRenderer> : message.content}
                        {message.meta?.interrupted === true && (
                          <div className="message-interrupted">已停止生成</div>
                        )}
                      </div>
                    </article>
                  )
              })
            )}
          </section>
          {showBackToLatest && (
            <button type="button" className="back-to-latest" onClick={() => scrollToLatest('smooth')}>
              回到最新 ↓
            </button>
          )}
        </div>

        <footer className="chat-input-wrap" data-guide="composer">
          {error && <div className="inline-error">{error}</div>}
          <div className="chat-input-box">
            <textarea
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && event.ctrlKey) {
                  event.preventDefault()
                  send()
                }
              }}
              placeholder="输入消息...（Ctrl+Enter 发送，Enter 换行）"
              disabled={streaming}
            />
            <button
              className={streaming ? 'send-btn stop' : 'send-btn'}
              onClick={streaming ? stopGeneration : send}
              disabled={!sessionId || (!streaming && !input.trim())}
            >
              {streaming ? '停止' : '发送'}
            </button>
          </div>
        </footer>
      </main>

      <div className="resize-handle" onMouseDown={startResize} />

      <aside className="file-view-panel" data-guide="viewer">
        <header className="editor-tabs">
          <div className={selectedFile ? 'editor-tab active' : 'editor-tab'}>
            <span>{selectedFile?.name || '欢迎'}</span>
            {selectedFile && (
              <button
                type="button"
                className="editor-tab-close"
                onClick={() => {
                  setSelectedFile(null)
                  setFileContent(null)
                  setEditing(false)
                }}
              >
                ×
              </button>
            )}
          </div>
          {fileContent?.markdown && (
            <button type="button" className="editor-action" onClick={() => setEditing((value) => !value)}>
              {editing ? '预览' : '编辑'}
            </button>
          )}
        </header>

        <div className="file-view">
          {!selectedFile && (
            <div className="welcome-card">
              <div className="welcome-title">Workmode Public</div>
              <p className="welcome-subtitle">纯净科研工作助手 · 本地项目工作台</p>
              <section className="welcome-section">
                <h2>可以做什么</h2>
                <ul>
                  <li>固定注入项目协议：在项目根 WORKMODE.md 中写 @docs/protocol.md</li>
                  <li>阅读 Markdown / 代码 / UTF-8 文本</li>
                  <li>预览 PDF 和图片</li>
                  <li>编辑已存在的 Markdown 文件</li>
                </ul>
              </section>
            </div>
          )}
          {selectedFile?.preview === 'unsupported' && <div className="file-view-error">该格式不在安全预览白名单内。</div>}
          {selectedFile?.preview === 'media' && activeSlug && (
            isPdf(selectedFile.path)
              ? <iframe className="media pdf" src={api.mediaUrl(activeSlug, selectedFile.path)} title={selectedFile.name} />
              : isImage(selectedFile.path)
                ? <img className="media image" src={api.mediaUrl(activeSlug, selectedFile.path)} alt={selectedFile.name} />
                : <div className="file-view-error">暂不支持该媒体格式。</div>
          )}
          {fileContent && !editing && (
            fileContent.markdown
              ? <article className="file-view-markdown"><MarkdownRenderer>{fileContent.content}</MarkdownRenderer></article>
              : <pre className="file-view-pre">{fileContent.content}</pre>
          )}
          {fileContent && editing && (
            <div className="file-editor">
              <textarea value={fileDraft} onChange={(event) => setFileDraft(event.target.value)} />
              <button className="project-create-submit" onClick={saveFile}>保存 Markdown</button>
            </div>
          )}
        </div>
      </aside>

      <footer className="status-bar">
        <span className="status-segment">
          <span className="status-dot ok" aria-hidden />
          后端 ok
        </span>
        <span className="status-segment status-segment-meta">
          {activeProject ? `项目 · ${activeProject.name}` : '未打开项目'}
        </span>
        <span className="status-segment status-segment-meta">
          会话 · {sessionId ? sessionId.slice(0, 8) : '未开始'}
        </span>
        <span className="status-segment status-segment-meta">{status}</span>
      </footer>

      <FirstRunWizard
        stage={onboardingProgress.stage}
        draft={{
          model_base_url: settingsDraft.model_base_url,
          model_name: settingsDraft.model_name,
          model_api_key: settingsDraft.model_api_key
        } satisfies ModelDraft}
        savedKey={Boolean(settings?.model_api_key_set)}
        busy={modelTesting || pickingFolder || installingTutorial}
        connectionStatus={modelTestStatus}
        connectionOk={modelTestOk}
        onDraftChange={(draft) => {
          setSettingsDraft((previous) => ({ ...previous, ...draft }))
          setModelTestOk(false)
          setModelTestStatus('')
        }}
        onNext={() => setOnboardingStage(onboardingProgress.stage === 'welcome' ? 'model' : 'choice')}
        onBack={() => setOnboardingStage(onboardingProgress.stage === 'choice' ? 'model' : 'welcome')}
        onSkip={() => setOnboardingStage('complete', 0)}
        onTestAndSave={() => testModelConnection(true)}
        onChooseTutorial={() => createTutorialProject(true)}
        onChooseProject={chooseOwnProjectFromOnboarding}
      />

      {onboardingProgress.stage === 'tour' && (
        <GuidedTour
          step={onboardingProgress.tourStep}
          onStep={(tourStep) => setOnboardingProgress((previous) => ({ ...previous, tourStep }))}
          onDone={() => setOnboardingStage('complete', 0)}
          onSkip={() => setOnboardingStage('complete', 0)}
        />
      )}

      {activeProject?.is_tutorial && onboardingProgress.stage === 'complete' && (
        <TutorialChecklist
          progress={onboardingProgress}
          collapsed={tutorialChecklistCollapsed}
          onCollapsed={setTutorialChecklistCollapsed}
          onTask={handleTutorialTask}
          onOpenProject={openProjectAfterTutorial}
          onResetTutorial={resetTutorialProject}
        />
      )}

      {achievementToast && <AchievementToast achievement={achievementToast} />}
    </div>
  )
}
