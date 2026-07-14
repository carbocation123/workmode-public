import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const css = new TextDecoder().decode(readFileSync(new URL('./styles.css', import.meta.url)))

function ruleBody(selector: string): string {
  const start = css.indexOf(`${selector} {`)
  if (start < 0) throw new Error(`Missing CSS rule for ${selector}`)
  const bodyStart = css.indexOf('{', start) + 1
  const bodyEnd = css.indexOf('}', bodyStart)
  return css.slice(bodyStart, bodyEnd)
}

function lastRuleBody(selector: string): string {
  const start = css.lastIndexOf(`${selector} {`)
  if (start < 0) throw new Error(`Missing CSS rule for ${selector}`)
  const bodyStart = css.indexOf('{', start) + 1
  const bodyEnd = css.indexOf('}', bodyStart)
  return css.slice(bodyStart, bodyEnd)
}

describe('literature theme color contract', () => {
  it('defines semantic colors for controls, floating surfaces, overlays and code areas', () => {
    expect(ruleBody(':root')).toContain('--lit-control-bg:')
    expect(ruleBody(':root')).toContain('--lit-control-hover:')
    expect(ruleBody(':root')).toContain('--lit-floating-bg:')
    expect(ruleBody(':root')).toContain('--lit-overlay-bg:')
    expect(ruleBody(':root')).toContain('--lit-code-bg:')
  })

  it('keeps literal fallback colors inside the root token contract only', () => {
    const componentCss = css.slice(css.indexOf('}') + 1)
    expect(componentCss).not.toMatch(/#[0-9a-f]{3,8}\b|rgba?\(/i)
  })

  it.each([
    ['session selector', '.session-switcher select', '--lit-control-bg'],
    ['context controls', '.compact-button, .memory-button, .notes-button', '--lit-control-bg'],
    ['modal close', '.modal-header > button', '--lit-control-bg'],
    ['notes header controls', '.notes-header-actions button', '--lit-control-bg'],
    ['notes document controls', '.note-document-toolbar > button, .note-mode-switch button', '--lit-control-bg'],
    ['filter controls', '.tag-filter-trigger, .clear-filter', '--lit-control-bg'],
    ['import controls', '.import-confirm-actions button', '--lit-control-bg'],
    ['composer', '.composer', '--lit-input-bg'],
    ['PDF workspace', '.pdf-workspace', '--lit-document-bg'],
  ])('%s consumes a semantic theme token', (_name, selector, token) => {
    const body = ruleBody(selector)
    expect(body).toContain(`var(${token})`)
    expect(body).not.toMatch(/background(?:-color)?:\s*(?:#[0-9a-f]{3,8}\b|rgba?\()/i)
  })

  it('reserves independent space for the project-notes icon and count badge', () => {
    expect(lastRuleBody('.notes-button')).toContain('width: 48px')
    expect(lastRuleBody('.notes-button')).toContain('gap: 4px')
    expect(ruleBody('.compact-button svg, .memory-button svg, .notes-button svg')).toContain('flex: 0 0 14px')
    expect(ruleBody('.notes-button em')).toContain('flex: 0 0 16px')
  })
})
