export const LITERATURE_ONBOARDING_STORAGE_KEY = 'workmode-public-literature-onboarding-v1'

export interface LiteratureOnboardingState {
  version: 1
  completed: boolean
  step: number
}

export const LITERATURE_ONBOARDING_STEPS = [
  'welcome',
  'import',
  'processing',
  'conversation',
] as const

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
