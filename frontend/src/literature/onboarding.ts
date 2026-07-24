export const LITERATURE_ONBOARDING_STORAGE_KEY = 'workmode-public-literature-onboarding-v1'

export interface LiteratureOnboardingState {
  version: 1
  completed: boolean
  step: number
}

export const LITERATURE_TOUR_STEPS = [
  {
    target: 'project',
    title: '当前文献项目',
    description: '文献按项目分开保存。点击项目名，可以新建或切换文献项目。',
  },
  {
    target: 'import',
    title: '把文献带进来',
    description: '从这里导入 PDF，也可以把 EndNote 文献库连同分组、标签和附件一起搬进来。',
  },
  {
    target: 'filters',
    title: '快速找到文献',
    description: '文献多起来后，可以按分组和标签筛选。',
  },
  {
    target: 'papers',
    title: '查看或选中文献',
    description: '点文献卡片查看详情；勾选左侧方框，就会把它加入当前对话。',
  },
  {
    target: 'composer',
    title: '直接告诉 AI 你想做什么',
    description: '例如「精读这篇」或「比较这些文献的结论」。Ctrl + Enter 发送。',
  },
] as const

export const LITERATURE_ONBOARDING_STEPS = LITERATURE_TOUR_STEPS.map((step) => step.target)

export const EMPTY_LITERATURE_ONBOARDING: LiteratureOnboardingState = {
  version: 1,
  completed: false,
  step: 0,
}

export function parseLiteratureOnboarding(raw: string | null): LiteratureOnboardingState {
  if (!raw) return { ...EMPTY_LITERATURE_ONBOARDING }
  try {
    const value = JSON.parse(raw) as Partial<LiteratureOnboardingState>
    if (value.version !== 1 || typeof value.completed !== 'boolean') {
      return { ...EMPTY_LITERATURE_ONBOARDING }
    }
    const step = Number.isFinite(value.step) ? Math.trunc(Number(value.step)) : 0
    return {
      version: 1,
      completed: value.completed,
      step: Math.min(Math.max(step, 0), LITERATURE_ONBOARDING_STEPS.length - 1),
    }
  } catch {
    return { ...EMPTY_LITERATURE_ONBOARDING }
  }
}

export function setLiteratureOnboardingStep(
  state: LiteratureOnboardingState,
  step: number,
): LiteratureOnboardingState {
  return {
    ...state,
    completed: false,
    step: Math.min(Math.max(Math.trunc(step), 0), LITERATURE_ONBOARDING_STEPS.length - 1),
  }
}

export function completeLiteratureOnboarding(
  state: LiteratureOnboardingState,
): LiteratureOnboardingState {
  return { ...state, completed: true }
}

export function resetLiteratureOnboarding(): LiteratureOnboardingState {
  return { ...EMPTY_LITERATURE_ONBOARDING }
}

export type LiteratureOnboardingMode = 'loading' | 'setup' | 'tour' | 'hidden'

export function literatureOnboardingMode(
  modelConfigured: boolean | null,
  state: LiteratureOnboardingState,
): LiteratureOnboardingMode {
  if (modelConfigured === null) return 'loading'
  if (!modelConfigured) return 'setup'
  return state.completed ? 'hidden' : 'tour'
}
