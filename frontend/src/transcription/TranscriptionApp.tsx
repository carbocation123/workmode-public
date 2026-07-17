import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { skinUsesChrome, type ActiveCustomSkin } from '../customSkin'
import { revealLocalItem } from '../desktop'
import { applicationHomeUrl, workbenchSettingsUrl } from '../literatureNavigation'
import { SkinChrome } from '../SkinChrome'
import { MarkdownRenderer } from '../MarkdownRenderer'
import { THEMES, type ThemeId } from '../theme'
import {
  formatDuration,
  formatTimestamp,
  nextSelectedJobId,
  sortJobs,
  statusLabel,
  type TranscriptSegment,
  type TranscriptionJob,
} from './model'
import {
  deleteJob,
  clearAiResult,
  generateAiResult,
  getWorkspaceInfo,
  listJobs,
  listTrash,
  readAiResults,
  readTranscript,
  renameJob,
  restoreJob,
  retryJob,
  transcriptFileUrl,
  uploadAudio,
  type DeletedTranscription,
  type TranscriptResult,
  type TranscriptionWorkspaceInfo,
  type TranscriptionAiKind,
  type TranscriptionAiResults,
} from './transcriptionApi'
import { TranscriptionOnboarding } from './TranscriptionOnboarding'
import {
  TRANSCRIPTION_ONBOARDING_STORAGE_KEY,
  parseTranscriptionOnboarding,
  resetTranscriptionOnboarding,
} from './onboarding'


interface TranscriptionAppProps {
  themeId: ThemeId
  customSkin: ActiveCustomSkin | null
}

type ResultTab = 'segments' | 'text' | 'markdown' | 'polished' | 'summary'
const SELECTED_JOB_KEY = 'workmode-transcription-selected-job'


function dateLabel(value: string): string {
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleString()
}


function segmentKey(segment: TranscriptSegment): string {
  return `${segment.seq}-${segment.start_ms}-${segment.end_ms}`
}


export default function TranscriptionApp({ themeId, customSkin }: TranscriptionAppProps) {
  const [workspace, setWorkspace] = useState<TranscriptionWorkspaceInfo | null>(null)
  const [jobs, setJobs] = useState<TranscriptionJob[]>([])
  const [selectedJobId, setSelectedJobId] = useState<string | null>(
    () => localStorage.getItem(SELECTED_JOB_KEY),
  )
  const [transcript, setTranscript] = useState<TranscriptResult | null>(null)
  const [aiResults, setAiResults] = useState<TranscriptionAiResults | null>(null)
  const [aiProcessing, setAiProcessing] = useState<TranscriptionAiKind | null>(null)
  const [aiConfirmKind, setAiConfirmKind] = useState<TranscriptionAiKind | null>(null)
  const [tab, setTab] = useState<ResultTab>('segments')
  const [loading, setLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [titleDraft, setTitleDraft] = useState('')
  const [renaming, setRenaming] = useState(false)
  const [trashOpen, setTrashOpen] = useState(false)
  const [trash, setTrash] = useState<DeletedTranscription[]>([])
  const [dragging, setDragging] = useState(false)
  const [guideOpen, setGuideOpen] = useState(() =>
    !parseTranscriptionOnboarding(localStorage.getItem(TRANSCRIPTION_ONBOARDING_STORAGE_KEY)).completed,
  )
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const selectedJobIdRef = useRef<string | null>(selectedJobId)

  const selectedJob = useMemo(
    () => jobs.find((job) => job.id === selectedJobId) || null,
    [jobs, selectedJobId],
  )
  const hasRunningJobs = jobs.some((job) => job.status === 'queued' || job.status === 'transcribing')
  const hudLayoutActive = Boolean(customSkin?.enabled && skinUsesChrome(customSkin.skin))
    || THEMES.some((theme) => theme.id === themeId && theme.layout === 'hud')

  const refreshJobs = useCallback(async () => {
    const nextJobs = sortJobs(await listJobs())
    setJobs(nextJobs)
    setSelectedJobId((current) => nextSelectedJobId(current, nextJobs))
    return nextJobs
  }, [])

  useEffect(() => {
    Promise.all([getWorkspaceInfo(), refreshJobs()])
      .then(([info]) => setWorkspace(info))
      .catch((reason) => setError(`转写模块连接失败：${reason instanceof Error ? reason.message : String(reason)}`))
      .finally(() => setLoading(false))
  }, [refreshJobs])

  useEffect(() => {
    selectedJobIdRef.current = selectedJobId
    if (selectedJobId) localStorage.setItem(SELECTED_JOB_KEY, selectedJobId)
    else localStorage.removeItem(SELECTED_JOB_KEY)
  }, [selectedJobId])

  useEffect(() => {
    setTitleDraft(selectedJob?.title || '')
    setTranscript(null)
    setAiResults(null)
    setTab('segments')
    if (!selectedJob || selectedJob.status !== 'completed') return
    let cancelled = false
    void Promise.all([readTranscript(selectedJob.id), readAiResults(selectedJob.id)])
      .then(([transcriptResult, aiResult]) => {
        if (!cancelled) {
          setTranscript(transcriptResult)
          setAiResults(aiResult)
        }
      })
      .catch((reason) => {
        if (!cancelled) setError(`转写结果读取失败：${reason instanceof Error ? reason.message : String(reason)}`)
      })
    return () => { cancelled = true }
  }, [selectedJob?.id, selectedJob?.status, selectedJob?.title])

  useEffect(() => {
    if (!hasRunningJobs) return
    const timer = window.setInterval(() => {
      void refreshJobs().catch((reason) => setError(String(reason)))
    }, 2500)
    return () => window.clearInterval(timer)
  }, [hasRunningJobs, refreshJobs])

  async function handleFiles(files: FileList | File[]) {
    const selected = Array.from(files)
    if (!selected.length || uploading) return
    if (!workspace?.dashscope_api_key_set) {
      setError('请先配置 DashScope API Key，再上传录音。')
      return
    }
    setUploading(true)
    setError('')
    setNotice('')
    const failures: string[] = []
    let lastCreated: TranscriptionJob | null = null
    for (let index = 0; index < selected.length; index += 1) {
      const file = selected[index]
      setUploadProgress(`正在导入 ${index + 1}/${selected.length}：${file.name}`)
      try {
        lastCreated = await uploadAudio(file)
      } catch (reason) {
        failures.push(`${file.name}：${reason instanceof Error ? reason.message : String(reason)}`)
      }
    }
    await refreshJobs()
    if (lastCreated) setSelectedJobId(lastCreated.id)
    setUploadProgress('')
    setUploading(false)
    if (failures.length) setError(failures.join('\n'))
    else setNotice(`已提交 ${selected.length} 个录音，Fun-ASR 将依次转写。`)
  }

  async function saveTitle() {
    if (!selectedJob || !titleDraft.trim() || renaming) return
    setRenaming(true)
    setError('')
    try {
      await renameJob(selectedJob.id, titleDraft.trim())
      await refreshJobs()
      setNotice('标题已更新。')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setRenaming(false)
    }
  }

  async function retrySelected() {
    if (!selectedJob) return
    setError('')
    try {
      await retryJob(selectedJob.id)
      setTranscript(null)
      setAiResults(null)
      await refreshJobs()
      setNotice('已重新提交转写。')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason))
    }
  }

  async function deleteSelected() {
    if (!selectedJob || !window.confirm(`删除「${selectedJob.title}」？录音和结果会移入模块回收站。`)) return
    setError('')
    try {
      await deleteJob(selectedJob.id)
      await refreshJobs()
      setTranscript(null)
      setAiResults(null)
      setNotice('记录已移入回收站。')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason))
    }
  }

  async function showTrash() {
    setTrashOpen(true)
    setError('')
    try {
      setTrash(await listTrash())
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason))
    }
  }

  async function restoreDeleted(item: DeletedTranscription) {
    setError('')
    try {
      const restored = await restoreJob(item.trash_id)
      setTrash(await listTrash())
      await refreshJobs()
      setSelectedJobId(restored.id)
      setNotice('转写记录已恢复。')
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason))
    }
  }

  async function openOutputFolder() {
    if (!selectedJob?.reveal_path) return
    try {
      const opened = await revealLocalItem(selectedJob.reveal_path)
      if (!opened) setNotice(`输出目录：${selectedJob.output_directory || selectedJob.output_path}`)
    } catch (reason) {
      setError(`打开文件夹失败：${reason instanceof Error ? reason.message : String(reason)}`)
    }
  }

  function requestAi(kind: TranscriptionAiKind) {
    if (!workspace?.model_api_configured) {
      setError('AI 模型尚未配置。请打开设置，填写模型 API 地址、API Key 和模型名称后再试。')
      return
    }
    setAiConfirmKind(kind)
  }

  async function confirmAi() {
    if (!selectedJob || !aiConfirmKind || aiProcessing) return
    const kind = aiConfirmKind
    const jobId = selectedJob.id
    setAiConfirmKind(null)
    setAiProcessing(kind)
    setError('')
    setNotice('')
    try {
      const result = await generateAiResult(jobId, kind)
      if (selectedJobIdRef.current === jobId) {
        setAiResults(result)
        setTab(kind === 'polish' ? 'polished' : 'summary')
        setNotice(kind === 'polish' ? 'AI 润色稿已生成并单独保存。' : 'AI 会议总结已生成并单独保存。')
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason))
    } finally {
      setAiProcessing(null)
    }
  }

  async function clearAi(kind: TranscriptionAiKind) {
    if (!selectedJob || aiProcessing) return
    const label = kind === 'polish' ? '润色稿' : '会议总结'
    const jobId = selectedJob.id
    if (!window.confirm(`清除当前 AI ${label}？原始转写不会受影响。`)) return
    setError('')
    try {
      const result = await clearAiResult(jobId, kind)
      if (selectedJobIdRef.current === jobId) {
        setAiResults(result)
        if (tab === (kind === 'polish' ? 'polished' : 'summary')) setTab('segments')
        setNotice(`已清除 AI ${label}，原始转写保持不变。`)
      }
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : String(reason))
    }
  }

  function replayGuide() {
    localStorage.setItem(
      TRANSCRIPTION_ONBOARDING_STORAGE_KEY,
      JSON.stringify(resetTranscriptionOnboarding()),
    )
    setGuideOpen(true)
  }

  return (
    <div className={`transcription-shell${hudLayoutActive ? ' hud-layout' : ''}`} data-skin-slot="transcription-shell">
      <div className="skin-background-layer" aria-hidden />
      <div className="skin-decoration-overlay" aria-hidden />
      {hudLayoutActive && (
        <SkinChrome
          themeId={themeId}
          customSkin={customSkin}
          projectName="会议录音转文字"
          projectPath={workspace?.path || '正在读取转写目录'}
          modelName="FUN-ASR"
          streaming={hasRunningJobs}
          status={error ? 'ATTENTION' : hasRunningJobs ? 'TRANSCRIBING' : 'READY'}
        />
      )}

      <header className="transcription-header" data-skin-slot="transcription-header">
        <div className="transcription-brand">
          <button type="button" onClick={() => window.location.assign(applicationHomeUrl(window.location.href))} aria-label="返回功能大厅">←</button>
          <div><span>FILE TOOL</span><strong>会议录音转文字</strong></div>
        </div>
        <div className="transcription-header-meta">
          <span>{workspace?.model || 'fun-asr'}</span>
          <span>{workspace?.path || '正在初始化目录…'}</span>
        </div>
        <div className="transcription-header-actions">
          <button type="button" onClick={replayGuide}>使用指引</button>
          <button type="button" onClick={() => void showTrash()}>回收站</button>
          <button type="button" onClick={() => window.location.assign(workbenchSettingsUrl(window.location.href, 'transcription'))}>设置</button>
          <button type="button" className="primary" onClick={() => fileInputRef.current?.click()} disabled={uploading || !workspace?.dashscope_api_key_set}>
            {uploading ? '正在上传…' : '上传录音'}
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept="audio/*,video/mp4,.m4a,.mp3,.wav,.ogg,.flac,.aac,.webm,.mp4"
            multiple
            hidden
            onChange={(event) => {
              if (event.target.files) void handleFiles(event.target.files)
              event.target.value = ''
            }}
          />
        </div>
      </header>

      <aside className="transcription-list-panel" data-skin-slot="transcription-list">
        <div className="transcription-list-heading">
          <div><span>FILES</span><strong>转写记录</strong></div>
          <small>{jobs.length} 个文件</small>
        </div>
        <button
          type="button"
          className={`transcription-drop-zone${dragging ? ' dragging' : ''}`}
          onClick={() => fileInputRef.current?.click()}
          onDragEnter={(event) => { event.preventDefault(); setDragging(true) }}
          onDragOver={(event) => event.preventDefault()}
          onDragLeave={() => setDragging(false)}
          onDrop={(event) => {
            event.preventDefault()
            setDragging(false)
            void handleFiles(event.dataTransfer.files)
          }}
          disabled={uploading || !workspace?.dashscope_api_key_set}
        >
          <strong>{workspace?.dashscope_api_key_set ? '拖入或选择录音' : '先配置 DashScope API Key'}</strong>
          <span>支持一次选择多个音频文件</span>
        </button>
        <div className="transcription-job-list">
          {jobs.map((job) => (
            <button
              type="button"
              key={job.id}
              className={`transcription-job${job.id === selectedJobId ? ' active' : ''}`}
              onClick={() => setSelectedJobId(job.id)}
            >
              <span className={`job-status-dot ${job.status}`} />
              <span className="job-copy">
                <strong>{job.title}</strong>
                <small>{job.original_name}</small>
                <span>{statusLabel(job.status)} · {dateLabel(job.updated_at)}</span>
              </span>
            </button>
          ))}
          {!loading && jobs.length === 0 && (
            <div className="transcription-empty-list">还没有转写文件。上传录音后，每个文件会在这里独立显示。</div>
          )}
        </div>
      </aside>

      <main className="transcription-result-panel" data-skin-slot="transcription-result">
        {selectedJob ? (
          <>
            <section className="transcription-result-header">
              <div className="title-editor">
                <input value={titleDraft} onChange={(event) => setTitleDraft(event.target.value)} aria-label="转写标题" />
                <button type="button" onClick={() => void saveTitle()} disabled={renaming || !titleDraft.trim() || titleDraft.trim() === selectedJob.title}>
                  {renaming ? '保存中…' : '保存标题'}
                </button>
              </div>
              <div className="result-meta">
                <span className={`status-badge ${selectedJob.status}`}>{statusLabel(selectedJob.status)}</span>
                <span>{formatDuration(selectedJob.duration_ms)}</span>
                <span>{selectedJob.model}</span>
                <span>{selectedJob.original_name}</span>
              </div>
              <div className="result-actions">
                <button type="button" onClick={() => void retrySelected()} disabled={selectedJob.status === 'queued' || selectedJob.status === 'transcribing'}>重新转写</button>
                <button type="button" onClick={() => void openOutputFolder()} disabled={selectedJob.status !== 'completed'}>打开输出文件夹</button>
                <button type="button" className="danger" onClick={() => void deleteSelected()} disabled={selectedJob.status === 'transcribing'}>删除记录</button>
              </div>
            </section>

            {selectedJob.status === 'completed' && transcript ? (
              <section className="transcription-document">
                <div className="transcription-ai-toolbar">
                  <div>
                    <strong>AI 文本处理</strong>
                    <span>{workspace?.model_api_configured
                      ? `使用 ${workspace.model_name}；仅手动触发，结果不会覆盖原文`
                      : '尚未配置 AI 模型；不影响查看和下载原始转写'}</span>
                  </div>
                  <div>
                    {!workspace?.model_api_configured && (
                      <button type="button" onClick={() => window.location.assign(workbenchSettingsUrl(window.location.href, 'transcription'))}>配置 AI 模型</button>
                    )}
                    <button type="button" onClick={() => requestAi('polish')} disabled={Boolean(aiProcessing)}>
                      {aiProcessing === 'polish' ? '正在润色…' : aiResults?.polished ? '重新生成润色' : 'AI 润色'}
                    </button>
                    {aiResults?.polished && <button type="button" onClick={() => void clearAi('polish')} disabled={Boolean(aiProcessing)}>清除润色</button>}
                    <button type="button" onClick={() => requestAi('summary')} disabled={Boolean(aiProcessing)}>
                      {aiProcessing === 'summary' ? '正在总结…' : aiResults?.summary ? '重新生成总结' : 'AI 总结'}
                    </button>
                    {aiResults?.summary && <button type="button" onClick={() => void clearAi('summary')} disabled={Boolean(aiProcessing)}>清除总结</button>}
                  </div>
                </div>
                <nav className="result-tabs" aria-label="结果格式">
                  <button type="button" className={tab === 'segments' ? 'active' : ''} onClick={() => setTab('segments')}>按说话人</button>
                  <button type="button" className={tab === 'text' ? 'active' : ''} onClick={() => setTab('text')}>纯文本</button>
                  <button type="button" className={tab === 'markdown' ? 'active' : ''} onClick={() => setTab('markdown')}>Markdown</button>
                  {aiResults?.polished && <button type="button" className={tab === 'polished' ? 'active' : ''} onClick={() => setTab('polished')}>AI 润色稿</button>}
                  {aiResults?.summary && <button type="button" className={tab === 'summary' ? 'active' : ''} onClick={() => setTab('summary')}>AI 总结</button>}
                  <span />
                  <a href={transcriptFileUrl(selectedJob.id, 'text')} download>下载 TXT</a>
                  <a href={transcriptFileUrl(selectedJob.id, 'markdown')} download>下载 MD</a>
                  <a href={transcriptFileUrl(selectedJob.id, 'json')} download>下载 JSON</a>
                  {aiResults?.polished && <a href={transcriptFileUrl(selectedJob.id, 'polished')} download>下载润色稿</a>}
                  {aiResults?.summary && <a href={transcriptFileUrl(selectedJob.id, 'summary')} download>下载总结</a>}
                </nav>
                <div className="transcription-document-body">
                  {tab === 'segments' && transcript.segments.map((segment) => (
                    <article className="transcript-segment" key={segmentKey(segment)}>
                      <div><strong>{segment.speaker}</strong><time>{formatTimestamp(segment.start_ms)}–{formatTimestamp(segment.end_ms)}</time>{segment.is_overlap && <span>重叠发言</span>}</div>
                      <p>{segment.text}</p>
                    </article>
                  ))}
                  {tab === 'text' && <pre>{transcript.text}</pre>}
                  {tab === 'markdown' && <pre>{transcript.markdown}</pre>}
                  {tab === 'polished' && aiResults?.polished && <div className="ai-result-markdown"><MarkdownRenderer>{aiResults.polished}</MarkdownRenderer></div>}
                  {tab === 'summary' && aiResults?.summary && <div className="ai-result-markdown"><MarkdownRenderer>{aiResults.summary}</MarkdownRenderer></div>}
                </div>
              </section>
            ) : (
              <section className={`transcription-pending-state ${selectedJob.status}`}>
                <span className="pending-pulse" />
                <strong>{statusLabel(selectedJob.status)}</strong>
                <p>{selectedJob.status === 'failed'
                  ? selectedJob.error || '转写失败，可以保留原始录音后重新提交。'
                  : '录音已经保存在 input 目录。任务完成后，TXT、Markdown 和 JSON 会写入对应 output 目录。'}</p>
              </section>
            )}
          </>
        ) : (
          <section className="transcription-welcome">
            <span>声</span>
            <h1>上传录音，等待转写</h1>
            <p>这个工具不创建项目或对话。它只管理固定目录中的录音与结果，根目录里的其他内容不会参与扫描。</p>
            <button type="button" onClick={() => fileInputRef.current?.click()} disabled={!workspace?.dashscope_api_key_set}>选择录音文件</button>
          </section>
        )}
      </main>

      <footer className="transcription-footer">
        <span>{uploadProgress || notice || (hasRunningJobs ? 'Fun-ASR 正在处理队列' : '准备就绪')}</span>
        <span>{workspace?.dashscope_api_key_set ? 'DashScope 已配置' : 'DashScope 尚未配置'}</span>
      </footer>

      {error && <div className="transcription-error" role="alert"><span>{error}</span><button type="button" onClick={() => setError('')}>×</button></div>}

      {trashOpen && (
        <div className="transcription-modal-backdrop" role="presentation" onMouseDown={() => setTrashOpen(false)}>
          <section className="transcription-trash-dialog" role="dialog" aria-modal="true" aria-labelledby="transcription-trash-title" onMouseDown={(event) => event.stopPropagation()}>
            <header><div><span>RECOVERY</span><h2 id="transcription-trash-title">转写回收站</h2></div><button type="button" onClick={() => setTrashOpen(false)}>×</button></header>
            <div className="trash-list">
              {trash.map((item) => (
                <article key={item.trash_id}>
                  <div><strong>{item.job.title}</strong><span>{item.job.original_name} · {dateLabel(item.deleted_at)}</span></div>
                  <button type="button" onClick={() => void restoreDeleted(item)}>恢复</button>
                </article>
              ))}
              {trash.length === 0 && <p>回收站为空。</p>}
            </div>
          </section>
        </div>
      )}

      {aiConfirmKind && selectedJob && (
        <div className="transcription-modal-backdrop" role="presentation" onMouseDown={() => setAiConfirmKind(null)}>
          <section className="transcription-ai-dialog" role="dialog" aria-modal="true" aria-labelledby="transcription-ai-title" onMouseDown={(event) => event.stopPropagation()}>
            <span>MANUAL AI</span>
            <h2 id="transcription-ai-title">确认{aiConfirmKind === 'polish' ? '润色转写' : '生成会议总结'}</h2>
            <p>会把当前转写文本发送给你配置的模型服务，可能产生费用。不会覆盖原始转写；生成结果会作为独立 Markdown 文件保存在本次 output 目录。</p>
            <ul>
              <li>当前模型：{workspace?.model_name || '未识别'}</li>
              <li>请确认转写内容允许发送给该模型服务</li>
              <li>AI 可能出错，重要结论和行动项仍需人工核对</li>
            </ul>
            <div>
              <button type="button" onClick={() => setAiConfirmKind(null)}>取消</button>
              <button type="button" className="primary" onClick={() => void confirmAi()}>确认并开始</button>
            </div>
          </section>
        </div>
      )}

      {guideOpen && (
        <TranscriptionOnboarding
          dashscopeConfigured={Boolean(workspace?.dashscope_api_key_set)}
          modelConfigured={Boolean(workspace?.model_api_configured)}
          onConfigure={() => window.location.assign(workbenchSettingsUrl(window.location.href, 'transcription'))}
          onClose={() => setGuideOpen(false)}
        />
      )}
    </div>
  )
}
