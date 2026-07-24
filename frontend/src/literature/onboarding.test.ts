import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

import {
  EMPTY_LITERATURE_ONBOARDING,
  LITERATURE_ONBOARDING_STEPS,
  LITERATURE_TOUR_STEPS,
  completeLiteratureOnboarding,
  literatureOnboardingMode,
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
    const guide = new TextDecoder().decode(readFileSync(new URL('./LiteratureOnboarding.tsx', import.meta.url)))
    const workbench = new TextDecoder().decode(readFileSync(new URL('../App.tsx', import.meta.url)))

    expect(literature).toContain('<LiteratureOnboarding')
    expect(literature).toContain('data-literature-guide="settings"')
    expect(literature).toContain('data-literature-guide="project"')
    expect(literature).toContain('data-literature-guide="import"')
    expect(literature).toContain('data-literature-guide="filters"')
    expect(literature).toContain('data-literature-guide="papers"')
    expect(literature).toContain('data-literature-guide="composer"')
    expect(guide).toContain('literature-tour-spotlight')
    expect(guide).toContain('先配置 DeepSeek API')
    expect(guide).not.toContain('literature-onboarding-modal')
    expect(guide).not.toContain('MINERU_SETUP')
    expect(workbench).toContain('settings-section-mineru')
    expect(workbench).toContain('重新播放文献模式引导')
    expect(workbench).toContain('settingsReturnSurface === null && <FirstRunWizard')
    expect(workbench).toContain("settingsReturnSurface === null && onboardingProgress.stage === 'tour'")
  })

  it('requires model configuration before the interface tour and hides after completion', () => {
    expect(literatureOnboardingMode(null, EMPTY_LITERATURE_ONBOARDING)).toBe('loading')
    expect(literatureOnboardingMode(false, EMPTY_LITERATURE_ONBOARDING)).toBe('setup')
    expect(literatureOnboardingMode(true, EMPTY_LITERATURE_ONBOARDING)).toBe('tour')
    expect(literatureOnboardingMode(true, completeLiteratureOnboarding(EMPTY_LITERATURE_ONBOARDING))).toBe('hidden')
  })

  it('keeps every tour step short and anchored to the real literature interface', () => {
    expect(LITERATURE_TOUR_STEPS.map((step) => step.target)).toEqual([
      'project',
      'import',
      'filters',
      'papers',
      'composer',
    ])
    for (const step of LITERATURE_TOUR_STEPS) {
      expect(step.description.length).toBeLessThanOrEqual(56)
    }
  })
})
