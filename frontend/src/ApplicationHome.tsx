import { useEffect, useMemo, useState } from 'react'

import { api, type Project } from './api'
import { skinUsesChrome, type ActiveCustomSkin } from './customSkin'
import { prepareLiteratureWorkbench } from './literatureLauncher'
import { transcriptionWorkbenchUrl, workbenchUrl, writingWorkbenchUrl } from './literatureNavigation'
import { SkinChrome } from './SkinChrome'
import { THEMES, type ThemeId } from './theme'

interface ApplicationHomeProps {
  themeId: ThemeId
  customSkin: ActiveCustomSkin | null
}

export default function ApplicationHome({ themeId, customSkin }: ApplicationHomeProps) {
  const [projects, setProjects] = useState<Project[]>([])
  const [activeSlug, setActiveSlug] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [openingLiterature, setOpeningLiterature] = useState(false)
  const [error, setError] = useState('')

  async function refreshProjects() {
    const payload = await api.projects()
    setProjects(payload.projects)
    setActiveSlug(payload.active_slug)
  }

  useEffect(() => {
    void refreshProjects()
      .catch((reason) => setError(`项目状态读取失败：${reason instanceof Error ? reason.message : String(reason)}`))
      .finally(() => setLoading(false))
  }, [])

  const activeProject = useMemo(
    () => projects.find((project) => project.slug === activeSlug) || null,
    [activeSlug, projects],
  )
  const literatureProjects = projects.filter((project) => project.project_type === 'literature-library')
  const hudLayoutActive = Boolean(customSkin?.enabled && skinUsesChrome(customSkin.skin))
    || THEMES.some((theme) => theme.id === themeId && theme.layout === 'hud')

  async function openLiterature() {
    if (openingLiterature) return
    setOpeningLiterature(true)
    setError('')
    try {
      const url = await prepareLiteratureWorkbench(window.location.href, {
        projects,
        activeProject,
      })
      if (url) window.location.assign(url)
    } catch (reason) {
      setError(`文献智库打开失败：${reason instanceof Error ? reason.message : String(reason)}`)
    } finally {
      setOpeningLiterature(false)
    }
  }

  return (
    <main className={`mode-hub-shell${hudLayoutActive ? ' hud-layout' : ''}`} data-skin-slot="feature-hub">
      <div className="skin-background-layer" aria-hidden />
      <div className="skin-decoration-overlay" aria-hidden />
      {hudLayoutActive && (
        <SkinChrome
          themeId={themeId}
          customSkin={customSkin}
          projectName={activeProject?.name || '功能大厅'}
          projectPath={loading ? '正在扫描本地项目' : `${projects.length} 个本地项目 · 选择工作流入口`}
          modelName="WORKMODE CORE"
          streaming={openingLiterature}
          status={error ? 'ATTENTION' : loading ? 'SCANNING' : 'READY'}
        />
      )}
      <header className="mode-hub-header" data-skin-slot="feature-hub-header">
        <div className="mode-hub-brand">
          <span className="mode-hub-mark">W</span>
          <div><strong>WORKMODE</strong><small>科研协作入口</small></div>
        </div>
        <div className="mode-hub-status">
          <span>{loading ? '正在读取项目…' : `${projects.length} 个本地项目`}</span>
          <span>{activeProject ? `最近：${activeProject.name}` : '尚未选择项目'}</span>
        </div>
      </header>

      <section className="mode-hub-grid" aria-label="功能入口">
        <button
          type="button"
          className="mode-card mode-card-workbench"
          data-skin-slot="feature-card"
          onClick={() => window.location.assign(workbenchUrl(window.location.href))}
        >
          <span className="mode-card-index">01 / POWER USER</span>
          <span className="mode-card-icon">⌘</span>
          <strong>科研工作台</strong>
          <p>定制你自己的AI工作流</p>
          <span className="mode-card-meta">完整 Workmode · {projects.filter((project) => project.project_type !== 'literature-library').length} 个普通项目</span>
          <span className="mode-card-enter">进入工作台 →</span>
        </button>

        <button
          type="button"
          className="mode-card mode-card-literature"
          data-skin-slot="feature-card"
          onClick={() => void openLiterature()}
          disabled={openingLiterature}
        >
          <span className="mode-card-index">02 / SPECIALIZED</span>
          <span className="mode-card-icon">文</span>
          <strong>文献智库</strong>
          <p>拖入 PDF、结构化处理、标签筛选、文献讨论与笔记整理。适合轻量、固定的文献工作流。</p>
          <span className="mode-card-meta">文献特化模块 · {literatureProjects.length} 个文献项目</span>
          <span className="mode-card-enter">{openingLiterature ? '正在打开…' : '进入文献智库 →'}</span>
        </button>

        <button
          type="button"
          className="mode-card mode-card-transcription"
          data-skin-slot="feature-card"
          onClick={() => window.location.assign(transcriptionWorkbenchUrl(window.location.href))}
        >
          <span className="mode-card-index">03 / FILE TOOL</span>
          <span className="mode-card-icon">声</span>
          <strong>会议录音转文字</strong>
          <p>批量上传录音，使用 Fun-ASR 区分说话人，并集中查看与导出转写结果。</p>
          <span className="mode-card-meta">独立文件工具 · 不创建项目或对话</span>
          <span className="mode-card-enter">打开转写工具 →</span>
        </button>

        <button
          type="button"
          className="mode-card mode-card-writing"
          data-skin-slot="feature-card"
          onClick={() => window.location.assign(writingWorkbenchUrl(window.location.href))}
        >
          <span className="mode-card-index">04 / TEXT TOOL</span>
          <span className="mode-card-icon">笔</span>
          <strong>文章处理</strong>
          <p>粘贴文字进行学术润色，或核查长文中的证据链、逻辑与表述一致性。</p>
          <span className="mode-card-meta">本地处理历史 · 不创建项目或对话</span>
          <span className="mode-card-enter">打开文章处理 →</span>
        </button>
      </section>

      <footer className="mode-hub-footer">
        <span>本地文件优先 · 项目会话仅由工作台管理</span>
        <span>转写与文章工具均不创建 Workmode 会话</span>
      </footer>
      {error && <div className="mode-hub-error" role="alert">{error}</div>}
    </main>
  )
}
