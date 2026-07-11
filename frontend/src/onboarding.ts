export const ONBOARDING_STORAGE_KEY = 'workmode-public-onboarding-v1'

export type OnboardingStage = 'welcome' | 'model' | 'choice' | 'tour' | 'complete'

export type ProductEvent =
  | 'model_connected'
  | 'project_created'
  | 'pdf_opened'
  | 'message_sent'
  | 'web_researched'
  | 'analysis_run'
  | 'markdown_saved'
  | 'context_viewed'
  | 'context_compacted'
  | 'tutorial_completed'

export type TutorialTaskId =
  | 'open_pdf'
  | 'ask_ai'
  | 'web_research'
  | 'run_analysis'
  | 'edit_markdown'
  | 'view_context'

export interface AchievementDefinition {
  id: string
  icon: string
  title: string
  description: string
  event: ProductEvent
}

export interface TutorialTaskDefinition {
  id: TutorialTaskId
  title: string
  description: string
  event: ProductEvent
  prompt?: string
}

export interface OnboardingProgress {
  version: 1
  stage: OnboardingStage
  tourStep: number
  tutorialTasks: TutorialTaskId[]
  achievements: Record<string, string>
}

export type DeepSeekModel = 'deepseek-v4-pro' | 'deepseek-v4-flash'

export interface ModelPresetDraft {
  model_base_url: string
  model_name: string
  model_api_key: string
}

export const DEEPSEEK_SETUP = {
  signInUrl: 'https://platform.deepseek.com/sign_in',
  apiKeysUrl: 'https://platform.deepseek.com/api_keys',
  topUpUrl: 'https://platform.deepseek.com/top_up',
  docsUrl: 'https://api-docs.deepseek.com/',
  pricingUrl: 'https://api-docs.deepseek.com/quick_start/pricing/',
  baseUrl: 'https://api.deepseek.com',
  models: ['deepseek-v4-pro', 'deepseek-v4-flash'] as DeepSeekModel[]
}

export function applyDeepSeekPreset<T extends ModelPresetDraft>(draft: T, model: DeepSeekModel): T {
  return {
    ...draft,
    model_base_url: DEEPSEEK_SETUP.baseUrl,
    model_name: model
  }
}

export const ACHIEVEMENTS: AchievementDefinition[] = [
  { id: 'engine_online', icon: '◉', title: '引擎点亮', description: '成功连接第一个模型 API', event: 'model_connected' },
  { id: 'project_home', icon: '▣', title: '建立基地', description: '创建或打开第一个科研项目', event: 'project_created' },
  { id: 'paper_opened', icon: '▤', title: '翻开论文', description: '在项目中打开一篇 PDF', event: 'pdf_opened' },
  { id: 'first_task', icon: '→', title: '第一次协作', description: '向科研助手发送第一个任务', event: 'message_sent' },
  { id: 'web_explorer', icon: '⌁', title: '文献侦察', description: '完成一次公开网页检索', event: 'web_researched' },
  { id: 'data_runner', icon: 'λ', title: '数据开工', description: '运行一次项目脚本或分析命令', event: 'analysis_run' },
  { id: 'markdown_coauthor', icon: '✎', title: '共同执笔', description: '保存一次 Markdown 修改', event: 'markdown_saved' },
  { id: 'context_reader', icon: '◫', title: '看见上下文', description: '查看当前上下文用量与组成', event: 'context_viewed' },
  { id: 'light_pack', icon: '↯', title: '轻装续航', description: '手动压缩一次长对话上下文', event: 'context_compacted' },
  { id: 'tutorial_graduate', icon: '◆', title: '科研协作入门', description: '完成官方教程的六项体验', event: 'tutorial_completed' }
]

export const TUTORIAL_TASKS: TutorialTaskDefinition[] = [
  { id: 'open_pdf', title: '打开一篇 PDF', description: '从左侧文件树打开教程中的真实论文', event: 'pdf_opened' },
  {
    id: 'ask_ai',
    title: '向 AI 提问',
    description: '让助手先介绍论文或项目内容',
    event: 'message_sent',
    prompt: '请先介绍这个教程项目的结构，并告诉我建议从哪个任务开始。'
  },
  {
    id: 'web_research',
    title: '检索相关资料',
    description: '让助手调用 web_search 完成一次公开网页检索',
    event: 'web_researched',
    prompt: '请围绕教程论文的核心主题做一次并行网络检索，列出可靠来源和链接。'
  },
  {
    id: 'run_analysis',
    title: '运行数据分析',
    description: '使用项目脚本分析示例实验数据',
    event: 'analysis_run',
    prompt: '请查看 data/raw/activity-run-001.csv 和 scripts/analyze_activity.py，运行脚本并解释结果。'
  },
  { id: 'edit_markdown', title: '保存 Markdown', description: '打开一份 Markdown，编辑并保存', event: 'markdown_saved' },
  { id: 'view_context', title: '查看上下文', description: '点击聊天顶部的 token 指示条查看组成', event: 'context_viewed' }
]

export const EMPTY_PROGRESS: OnboardingProgress = {
  version: 1,
  stage: 'welcome',
  tourStep: 0,
  tutorialTasks: [],
  achievements: {}
}

const STAGES = new Set<OnboardingStage>(['welcome', 'model', 'choice', 'tour', 'complete'])
const TASK_IDS = new Set(TUTORIAL_TASKS.map((item) => item.id))
const ACHIEVEMENT_IDS = new Set(ACHIEVEMENTS.map((item) => item.id))

export function parseProgress(raw: string | null): OnboardingProgress {
  if (!raw) return { ...EMPTY_PROGRESS, tutorialTasks: [], achievements: {} }
  try {
    const parsed = JSON.parse(raw) as Partial<OnboardingProgress>
    const stage = STAGES.has(parsed.stage as OnboardingStage) ? parsed.stage as OnboardingStage : 'welcome'
    const tutorialTasks = Array.isArray(parsed.tutorialTasks)
      ? parsed.tutorialTasks.filter((id): id is TutorialTaskId => TASK_IDS.has(id as TutorialTaskId))
      : []
    const achievements = Object.fromEntries(
      Object.entries(parsed.achievements || {})
        .filter(([id, timestamp]) => ACHIEVEMENT_IDS.has(id) && typeof timestamp === 'string')
    )
    return {
      version: 1,
      stage,
      tourStep: Number.isInteger(parsed.tourStep) ? Math.max(0, Number(parsed.tourStep)) : 0,
      tutorialTasks: [...new Set(tutorialTasks)],
      achievements
    }
  } catch {
    return { ...EMPTY_PROGRESS, tutorialTasks: [], achievements: {} }
  }
}

export function applyProductEvent(
  previous: OnboardingProgress,
  event: ProductEvent,
  timestamp = new Date().toISOString()
): { progress: OnboardingProgress; newAchievement: AchievementDefinition | null } {
  const task = TUTORIAL_TASKS.find((item) => item.event === event)
  const achievement = ACHIEVEMENTS.find((item) => item.event === event) || null
  const tutorialTasks = task && !previous.tutorialTasks.includes(task.id)
    ? [...previous.tutorialTasks, task.id]
    : [...previous.tutorialTasks]
  let newAchievement: AchievementDefinition | null = null
  const achievements = { ...previous.achievements }
  if (achievement && !achievements[achievement.id]) {
    achievements[achievement.id] = timestamp
    newAchievement = achievement
  }
  return {
    progress: { ...previous, tutorialTasks, achievements },
    newAchievement
  }
}

export function resetTutorialTasks(progress: OnboardingProgress): OnboardingProgress {
  return { ...progress, tutorialTasks: [] }
}

export function tutorialComplete(progress: OnboardingProgress): boolean {
  return TUTORIAL_TASKS.every((task) => progress.tutorialTasks.includes(task.id))
}
