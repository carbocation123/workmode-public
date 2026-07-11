import { describe, expect, it } from 'vitest'
import {
  DEFAULT_THEME_PREFERENCE,
  THEMES,
  allowedThemeSelection,
  parseThemePreference,
  resolveTheme,
  themeIsUnlocked
} from './theme'

describe('theme preferences', () => {
  it('repairs malformed local preferences to the stable laboratory default', () => {
    expect(parseThemePreference(null)).toEqual(DEFAULT_THEME_PREFERENCE)
    expect(parseThemePreference('{broken')).toEqual(DEFAULT_THEME_PREFERENCE)
    expect(parseThemePreference(JSON.stringify({ selection: 'unknown', reduceMotion: 'yes' }))).toEqual(DEFAULT_THEME_PREFERENCE)
  })

  it('resolves follow-system without changing explicit selections', () => {
    expect(resolveTheme('system', true)).toBe('observatory')
    expect(resolveTheme('system', false)).toBe('paper')
    expect(resolveTheme('high-contrast', false)).toBe('high-contrast')
  })

  it('keeps accessibility themes available and unlocks Origin Ring after tutorial graduation', () => {
    const origin = THEMES.find((theme) => theme.id === 'origin-ring')!
    const neonSpace = THEMES.find((theme) => theme.id === 'neon-space-lab')!
    const paper = THEMES.find((theme) => theme.id === 'paper')!
    const contrast = THEMES.find((theme) => theme.id === 'high-contrast')!

    expect(themeIsUnlocked(origin, {})).toBe(false)
    expect(themeIsUnlocked(neonSpace, {})).toBe(false)
    expect(themeIsUnlocked(origin, { tutorial_graduate: '2026-07-11T00:00:00Z' })).toBe(true)
    expect(themeIsUnlocked(neonSpace, { tutorial_graduate: '2026-07-11T00:00:00Z' })).toBe(true)
    expect(themeIsUnlocked(paper, {})).toBe(true)
    expect(themeIsUnlocked(contrast, {})).toBe(true)
    expect(allowedThemeSelection('origin-ring', {})).toBe('lab')
    expect(allowedThemeSelection('origin-ring', { tutorial_graduate: '2026-07-11T00:00:00Z' })).toBe('origin-ring')
    expect(allowedThemeSelection('neon-space-lab', { tutorial_graduate: '2026-07-11T00:00:00Z' })).toBe('neon-space-lab')
  })

  it('preserves valid local preferences including reduced motion', () => {
    expect(parseThemePreference(JSON.stringify({
      version: 1,
      selection: 'paper',
      reduceMotion: true
    }))).toEqual({ version: 1, selection: 'paper', reduceMotion: true })
  })
})
