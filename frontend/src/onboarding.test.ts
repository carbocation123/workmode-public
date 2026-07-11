import { describe, expect, it } from 'vitest'
import {
  ACHIEVEMENTS,
  DEEPSEEK_SETUP,
  EMPTY_PROGRESS,
  applyDeepSeekPreset,
  applyProductEvent,
  parseProgress
} from './onboarding'

describe('onboarding progress', () => {
  it('unlocks achievements and tutorial tasks from real product actions', () => {
    const connected = applyProductEvent(EMPTY_PROGRESS, 'model_connected', '2026-07-11T00:00:00Z')
    const opened = applyProductEvent(connected.progress, 'pdf_opened', '2026-07-11T00:01:00Z')
    const researched = applyProductEvent(opened.progress, 'web_researched', '2026-07-11T00:02:00Z')

    expect(connected.newAchievement?.id).toBe('engine_online')
    expect(opened.progress.tutorialTasks).toContain('open_pdf')
    expect(opened.newAchievement?.id).toBe('paper_opened')
    expect(researched.progress.tutorialTasks).toContain('web_research')
    expect(researched.newAchievement?.id).toBe('web_explorer')
  })

  it('keeps the first unlock time when the same event happens twice', () => {
    const first = applyProductEvent(EMPTY_PROGRESS, 'markdown_saved', '2026-07-11T00:00:00Z')
    const second = applyProductEvent(first.progress, 'markdown_saved', '2026-07-11T01:00:00Z')

    expect(second.newAchievement).toBeNull()
    expect(second.progress.achievements.markdown_coauthor).toBe('2026-07-11T00:00:00Z')
  })

  it('repairs malformed local state without losing known achievements', () => {
    const parsed = parseProgress(JSON.stringify({
      version: 999,
      stage: 'broken',
      achievements: { engine_online: '2026-07-11T00:00:00Z', unknown: 'x' },
      tutorialTasks: ['open_pdf', 'unknown']
    }))

    expect(parsed.stage).toBe('welcome')
    expect(parsed.achievements.engine_online).toBe('2026-07-11T00:00:00Z')
    expect(parsed.achievements.unknown).toBeUndefined()
    expect(parsed.tutorialTasks).toEqual(['open_pdf'])
    expect(ACHIEVEMENTS.length).toBeGreaterThanOrEqual(9)
  })

  it('provides current official DeepSeek setup links and safe presets', () => {
    expect(DEEPSEEK_SETUP.signInUrl).toBe('https://platform.deepseek.com/sign_in')
    expect(DEEPSEEK_SETUP.apiKeysUrl).toBe('https://platform.deepseek.com/api_keys')
    expect(DEEPSEEK_SETUP.topUpUrl).toBe('https://platform.deepseek.com/top_up')
    expect(DEEPSEEK_SETUP.baseUrl).toBe('https://api.deepseek.com')
    expect(DEEPSEEK_SETUP.models).toEqual(['deepseek-v4-pro', 'deepseek-v4-flash'])

    expect(applyDeepSeekPreset({
      model_base_url: 'https://old.example/v1',
      model_name: 'old-model',
      model_api_key: 'keep-this-local-key'
    }, 'deepseek-v4-pro')).toEqual({
      model_base_url: 'https://api.deepseek.com',
      model_name: 'deepseek-v4-pro',
      model_api_key: 'keep-this-local-key'
    })
  })
})
