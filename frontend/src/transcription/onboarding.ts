export const TRANSCRIPTION_ONBOARDING_STORAGE_KEY = 'workmode-public-transcription-onboarding-v2'

export interface TranscriptionOnboardingState {
  version: 2
  completed: boolean
  step: number
}

export const TRANSCRIPTION_ONBOARDING_STEPS = [
  'configure',
  'upload',
  'results',
  'ai',
] as const

export const EMPTY_TRANSCRIPTION_ONBOARDING: TranscriptionOnboardingState = {
  version: 2,
  completed: false,
  step: 0,
}

export function parseTranscriptionOnboarding(raw: string | null): TranscriptionOnboardingState {
  if (!raw) return { ...EMPTY_TRANSCRIPTION_ONBOARDING }
  try {
    const value = JSON.parse(raw) as Partial<TranscriptionOnboardingState>
    if (value.version !== 2 || typeof value.completed !== 'boolean') {
      return { ...EMPTY_TRANSCRIPTION_ONBOARDING }
    }
    const step = Number.isFinite(value.step) ? Math.trunc(Number(value.step)) : 0
    return {
      version: 2,
      completed: value.completed,
      step: Math.min(Math.max(step, 0), TRANSCRIPTION_ONBOARDING_STEPS.length - 1),
    }
  } catch {
    return { ...EMPTY_TRANSCRIPTION_ONBOARDING }
  }
}

export function setTranscriptionOnboardingStep(
  state: TranscriptionOnboardingState,
  step: number,
): TranscriptionOnboardingState {
  return {
    ...state,
    completed: false,
    step: Math.min(Math.max(Math.trunc(step), 0), TRANSCRIPTION_ONBOARDING_STEPS.length - 1),
  }
}

export function completeTranscriptionOnboarding(
  state: TranscriptionOnboardingState,
): TranscriptionOnboardingState {
  return { ...state, completed: true }
}

export function resetTranscriptionOnboarding(): TranscriptionOnboardingState {
  return { ...EMPTY_TRANSCRIPTION_ONBOARDING }
}
