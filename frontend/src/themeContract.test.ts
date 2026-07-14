import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

function read(relativePath: string): string {
  return new TextDecoder().decode(readFileSync(new URL(relativePath, import.meta.url)))
}

function ruleBody(css: string, selector: string): string {
  const escapedSelector = selector.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const match = new RegExp(`(?:^|\\n)${escapedSelector}\\s*\\{`).exec(css)
  if (!match || match.index < 0) throw new Error(`Missing CSS rule for ${selector}`)
  const start = match.index
  const bodyStart = css.indexOf('{', start) + 1
  const bodyEnd = css.indexOf('}', bodyStart)
  return css.slice(bodyStart, bodyEnd)
}

describe('shared application theme contract', () => {
  const contract = read('./themeContract.css')
  const mainEntry = read('./main.tsx')
  const literatureEntry = read('./literature/main.tsx')
  const workbenchCss = read('./styles.css')
  const hubCss = read('./applicationHome.css')
  const literatureCss = read('./literature/styles.css')

  it('defines shared semantic roles without literal component colors', () => {
    for (const token of [
      '--ui-app-background',
      '--ui-panel-background',
      '--ui-surface-background',
      '--ui-surface-raised',
      '--ui-control-background',
      '--ui-control-hover',
      '--ui-input-background',
      '--ui-floating-background',
      '--ui-overlay-background',
      '--ui-document-background',
      '--ui-code-background',
      '--ui-text',
      '--ui-text-muted',
      '--ui-border',
      '--ui-primary',
      '--ui-danger',
    ]) expect(contract).toContain(`${token}:`)
  })

  it('loads the contract in both Vite entry points before surface CSS', () => {
    expect(mainEntry.indexOf("import './themeContract.css'")).toBeGreaterThan(mainEntry.indexOf("import './styles.css'"))
    expect(mainEntry.indexOf("import './themeContract.css'")).toBeLessThan(mainEntry.indexOf("import './applicationHome.css'"))
    expect(literatureEntry.indexOf("import '../themeContract.css'")).toBeGreaterThan(literatureEntry.indexOf("import '../styles.css'"))
    expect(literatureEntry.indexOf("import '../themeContract.css'")).toBeLessThan(literatureEntry.indexOf("import './styles.css'"))
  })

  it('routes every application surface through the shared semantic roles', () => {
    expect(ruleBody(hubCss, '.mode-hub-shell')).toContain('var(--ui-app-background)')
    expect(ruleBody(hubCss, ':root')).toContain('--hub-panel: color-mix(in srgb, var(--ui-surface-background)')
    expect(ruleBody(hubCss, '.mode-card')).toContain('var(--hub-panel)')
    expect(ruleBody(workbenchCss, '.activity-bar')).toContain('var(--ui-panel-background)')
    expect(ruleBody(workbenchCss, '.side-panel')).toContain('var(--ui-panel-background)')
    expect(ruleBody(workbenchCss, '.ai-panel')).toContain('var(--ui-panel-background)')
    expect(ruleBody(workbenchCss, '.file-view-panel')).toContain('var(--ui-panel-background)')
    expect(ruleBody(workbenchCss, '.tool-card')).toContain('var(--ui-surface-background)')
    expect(ruleBody(workbenchCss, '.chat-input-box')).toContain('var(--ui-input-background)')
    expect(ruleBody(literatureCss, ':root')).toContain('--lit-control-bg: var(--ui-control-background)')
    expect(ruleBody(literatureCss, ':root')).toContain('--lit-document-bg: var(--ui-document-background)')
  })
})
