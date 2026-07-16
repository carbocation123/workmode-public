import { describe, expect, it } from 'vitest'

import {
  EMPTY_TRANSCRIPTION_ONBOARDING,
  TRANSCRIPTION_ONBOARDING_STEPS,
  completeTranscriptionOnboarding,
  parseTranscriptionOnboarding,
  resetTranscriptionOnboarding,
  setTranscriptionOnboardingStep,
} from './onboarding'

describe('meeting transcription onboarding', () => {
  it('repairs unknown local state and clamps the active step', () => {
    expect(parseTranscriptionOnboarding(null)).toEqual(EMPTY_TRANSCRIPTION_ONBOARDING)
    expect(parseTranscriptionOnboarding('{broken')).toEqual(EMPTY_TRANSCRIPTION_ONBOARDING)
    expect(parseTranscriptionOnboarding(JSON.stringify({ version: 1, completed: false, step: 99 })).step)
      .toBe(TRANSCRIPTION_ONBOARDING_STEPS.length - 1)
  })

  it('completes and replays without creating project files or sessions', () => {
    const moved = setTranscriptionOnboardingStep(EMPTY_TRANSCRIPTION_ONBOARDING, 1)
    expect(moved.step).toBe(1)
    expect(completeTranscriptionOnboarding(moved).completed).toBe(true)
    expect(resetTranscriptionOnboarding()).toEqual(EMPTY_TRANSCRIPTION_ONBOARDING)
  })
})
