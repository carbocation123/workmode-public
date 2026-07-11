import { describe, expect, it } from 'vitest'
import {
  ACHIEVEMENTS,
  EMPTY_PROGRESS,
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
})
