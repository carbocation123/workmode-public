import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import {
  EMPTY_LITERATURE_ONBOARDING,
  LITERATURE_ONBOARDING_STEPS,
  completeLiteratureOnboarding,
  parseLiteratureOnboarding,
  resetLiteratureOnboarding,
  setLiteratureOnboardingStep,
} from './onboarding'

describe('literature onboarding', () => {
  it('repairs unknown state and clamps the active step', () => {
    expect(parseLiteratureOnboarding(null)).toEqual(EMPTY_LITERATURE_ONBOARDING)
    expect(parseLiteratureOnboarding('{broken')).toEqual(EMPTY_LITERATURE_ONBOARDING)
    expect(parseLiteratureOnboarding(JSON.stringify({ version: 1, completed: false, step: 999 })).step)
      .toBe(LITERATURE_ONBOARDING_STEPS.length - 1)
  })

  it('can complete and replay independently from the workbench guide', () => {
    const moved = setLiteratureOnboardingStep(EMPTY_LITERATURE_ONBOARDING, 2)
    expect(moved.step).toBe(2)
    expect(completeLiteratureOnboarding(moved).completed).toBe(true)
    expect(resetLiteratureOnboarding()).toEqual(EMPTY_LITERATURE_ONBOARDING)
  })

  it('is mounted by the literature surface and replayable from shared settings', () => {
    const literature = new TextDecoder().decode(readFileSync(new URL('./LiteratureApp.tsx', import.meta.url)))
    const workbench = new TextDecoder().decode(readFileSync(new URL('../App.tsx', import.meta.url)))

    expect(literature).toContain('<LiteratureOnboarding')
    expect(workbench).toContain('settings-section-mineru')
    expect(workbench).toContain('重新播放文献模式引导')
    expect(workbench).toContain('settingsReturnSurface === null && <FirstRunWizard')
    expect(workbench).toContain("settingsReturnSurface === null && onboardingProgress.stage === 'tour'")
  })
})
