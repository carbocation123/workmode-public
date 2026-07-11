import { useEffect, useMemo, useState } from 'react'

import {
  ACHIEVEMENTS,
  TUTORIAL_TASKS,
  type AchievementDefinition,
  type OnboardingProgress,
  type OnboardingStage,
  type TutorialTaskId
} from './onboarding'

export interface ModelDraft {
  model_base_url: string
  model_name: string
  model_api_key: string
}

interface WizardProps {
  stage: OnboardingStage
  draft: ModelDraft
  savedKey: boolean
  busy: boolean
  connectionStatus: string
  connectionOk: boolean
  onDraftChange: (draft: ModelDraft) => void
  onNext: () => void
  onBack: () => void
  onSkip: () => void
  onTestAndSave: () => void
  onChooseTutorial: () => void
  onChooseProject: () => void
}

export function FirstRunWizard(props: WizardProps) {
  if (!['welcome', 'model', 'choice'].includes(props.stage)) return null
  return (
    <div className="onboarding-overlay" role="dialog" aria-modal="true" aria-label="首次使用引导">
      <section className="onboarding-dialog">
        <div className="onboarding-kicker">Workmode Public · 新手引导</div>
        {props.stage === 'welcome' && (
          <>
            <h1>把科研项目交给一个真正能动手的 AI</h1>
            <p>项目、对话和工作记忆保存在本机；模型请求会发送到你配置的 OpenAI-compatible API。</p>
            <div className="onboarding-feature-grid">
              <span>▣ 项目文件工作台</span><span>λ Python 与命令行</span>
              <span>▤ PDF / Markdown</span><span>◫ 可见上下文</span>
            </div>
            <div className="onboarding-actions">
              <button className="onboarding-secondary" onClick={props.onSkip}>暂时跳过</button>
              <button className="onboarding-primary" onClick={props.onNext}>开始设置</button>
            </div>
          </>
        )}
        {props.stage === 'model' && (
          <>
            <h1>连接你的模型 API</h1>
            <p>连接测试不会保存草稿；测试成功后才会把配置写入本机。</p>
            <label className="onboarding-field">
              <span>Base URL</span>
              <input value={props.draft.model_base_url} onChange={(event) => props.onDraftChange({ ...props.draft, model_base_url: event.target.value })} placeholder="https://api.example.com/v1" />
            </label>
            <label className="onboarding-field">
              <span>模型名称</span>
              <input value={props.draft.model_name} onChange={(event) => props.onDraftChange({ ...props.draft, model_name: event.target.value })} placeholder="模型 ID" />
            </label>
            <label className="onboarding-field">
              <span>API Key</span>
              <input type="password" value={props.draft.model_api_key} onChange={(event) => props.onDraftChange({ ...props.draft, model_api_key: event.target.value })} placeholder={props.savedKey ? '已保存；留空则沿用' : 'sk-…'} />
            </label>
            {props.connectionStatus && <div className={props.connectionOk ? 'onboarding-test success' : 'onboarding-test'}>{props.connectionStatus}</div>}
            <div className="onboarding-actions">
              <button className="onboarding-secondary" onClick={props.onBack}>上一步</button>
              <button className="onboarding-secondary" onClick={props.onNext}>跳过设置</button>
              <button className="onboarding-primary" onClick={props.onTestAndSave} disabled={props.busy}>
                {props.busy ? '正在测试…' : props.connectionOk ? '重新测试' : '测试连接并保存'}
              </button>
              <button className="onboarding-primary" onClick={props.onNext} disabled={!props.connectionOk}>下一步</button>
            </div>
          </>
        )}
        {props.stage === 'choice' && (
          <>
            <h1>从哪里开始？</h1>
            <p>第一次使用建议先体验教程。它使用独立示例文件，随时可以安全重置。</p>
            <div className="onboarding-choice-grid">
              <button onClick={props.onChooseTutorial} disabled={props.busy}>
                <strong>体验科研教程 <em>推荐</em></strong>
                <span>创建真实论文、示例实验数据和分析脚本，跟着六项任务走一遍。</span>
              </button>
              <button onClick={props.onChooseProject} disabled={props.busy}>
                <strong>打开自己的项目</strong>
                <span>选择电脑上的工作文件夹，然后播放界面指引。</span>
              </button>
            </div>
            <div className="onboarding-actions">
              <button className="onboarding-secondary" onClick={props.onBack}>上一步</button>
              <button className="onboarding-secondary" onClick={props.onSkip}>跳过引导</button>
            </div>
          </>
        )}
      </section>
    </div>
  )
}

const TOUR_STEPS = [
  { target: 'projects', title: '项目列表', description: '一个项目对应电脑上的一个真实文件夹。这里可以切换、创建或移除项目。' },
  { target: 'files', title: '项目文件', description: '从这里打开 Markdown、PDF、图片、代码和实验数据。文件仍保存在原位置。' },
  { target: 'chat', title: '对话时间线', description: 'AI 的正文和工具调用按真实顺序展示；接近底部时会自动跟随新消息。' },
  { target: 'context', title: '上下文指示', description: '点击 token 指示条，可以查看系统、工具、历史和固定导入分别占了多少。' },
  { target: 'viewer', title: '文件预览与编辑', description: 'PDF 和图片在这里预览；已有 Markdown 可以切换到编辑模式并保存。' },
  { target: 'composer', title: '发送与停止', description: '按 Ctrl+Enter 发送，Enter 换行。生成中同一个按钮会变成“停止”。' }
]

interface TourProps {
  step: number
  onStep: (step: number) => void
  onDone: () => void
  onSkip: () => void
}

export function GuidedTour({ step, onStep, onDone, onSkip }: TourProps) {
  const [rect, setRect] = useState<DOMRect | null>(null)
  const current = TOUR_STEPS[Math.min(step, TOUR_STEPS.length - 1)]
  useEffect(() => {
    function update() {
      const element = document.querySelector(`[data-guide="${current.target}"]`)
      setRect(element?.getBoundingClientRect() || null)
    }
    update()
    window.addEventListener('resize', update)
    return () => window.removeEventListener('resize', update)
  }, [current.target])

  return (
    <div className="guided-tour" role="dialog" aria-modal="true" aria-label={`界面指引：${current.title}`}>
      {rect && (
        <div className="guided-tour-spotlight" style={{ left: rect.left - 6, top: rect.top - 6, width: rect.width + 12, height: rect.height + 12 }} />
      )}
      <section className="guided-tour-card">
        <div className="guided-tour-count">{step + 1} / {TOUR_STEPS.length}</div>
        <h2>{current.title}</h2>
        <p>{current.description}</p>
        <div className="onboarding-actions">
          <button className="onboarding-secondary" onClick={onSkip}>跳过</button>
          {step > 0 && <button className="onboarding-secondary" onClick={() => onStep(step - 1)}>上一步</button>}
          <button className="onboarding-primary" onClick={() => step + 1 === TOUR_STEPS.length ? onDone() : onStep(step + 1)}>
            {step + 1 === TOUR_STEPS.length ? '开始体验' : '下一步'}
          </button>
        </div>
      </section>
    </div>
  )
}

interface ChecklistProps {
  progress: OnboardingProgress
  collapsed: boolean
  onCollapsed: (value: boolean) => void
  onTask: (taskId: TutorialTaskId, prompt?: string) => void
  onOpenProject: () => void
  onResetTutorial: () => void
}

export function TutorialChecklist(props: ChecklistProps) {
  const done = props.progress.tutorialTasks.length
  const complete = done === TUTORIAL_TASKS.length
  if (props.collapsed) {
    return <button className="tutorial-checklist-pill" onClick={() => props.onCollapsed(false)}>教程 {done}/{TUTORIAL_TASKS.length}</button>
  }
  return (
    <aside className="tutorial-checklist" aria-label="科研协作教程">
      <header>
        <div><strong>科研协作教程</strong><span>{done}/{TUTORIAL_TASKS.length}</span></div>
        <button onClick={() => props.onCollapsed(true)} title="收起">−</button>
      </header>
      <div className="tutorial-progress"><span style={{ width: `${done / TUTORIAL_TASKS.length * 100}%` }} /></div>
      {complete ? (
        <div className="tutorial-finished">
          <div className="tutorial-finished-icon">◆</div>
          <strong>教程完成</strong>
          <p>建议在新的正式项目中开始真实工作，避免教学内容污染上下文。</p>
          <button onClick={props.onOpenProject}>创建正式项目</button>
          <button onClick={props.onResetTutorial}>重置教程</button>
        </div>
      ) : (
        <ol>
          {TUTORIAL_TASKS.map((task) => {
            const checked = props.progress.tutorialTasks.includes(task.id)
            return (
              <li key={task.id} className={checked ? 'done' : ''}>
                <button onClick={() => props.onTask(task.id, task.prompt)} disabled={checked}>
                  <span className="tutorial-task-check">{checked ? '✓' : '○'}</span>
                  <span><strong>{task.title}</strong><small>{task.description}</small></span>
                </button>
              </li>
            )
          })}
        </ol>
      )}
    </aside>
  )
}

export function AchievementToast({ achievement }: { achievement: AchievementDefinition }) {
  return (
    <div className="achievement-toast" role="status">
      <span>{achievement.icon}</span>
      <div><small>成就解锁</small><strong>{achievement.title}</strong><p>{achievement.description}</p></div>
    </div>
  )
}

export function AchievementPanel({ progress }: { progress: OnboardingProgress }) {
  const unlocked = useMemo(() => Object.keys(progress.achievements).length, [progress.achievements])
  return (
    <div className="achievement-panel">
      <div className="achievement-panel-summary"><span>成就</span><strong>{unlocked}/{ACHIEVEMENTS.length}</strong></div>
      <div className="achievement-grid">
        {ACHIEVEMENTS.map((achievement) => {
          const timestamp = progress.achievements[achievement.id]
          return (
            <div key={achievement.id} className={timestamp ? 'achievement-card unlocked' : 'achievement-card'} title={timestamp ? new Date(timestamp).toLocaleString() : achievement.description}>
              <span>{achievement.icon}</span><div><strong>{timestamp ? achievement.title : '未解锁'}</strong><small>{achievement.description}</small></div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
