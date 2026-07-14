import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

function read(relativePath: string): string {
  return new TextDecoder().decode(readFileSync(new URL(relativePath, import.meta.url)))
}

describe('shared structural skin chrome across application surfaces', () => {
  const mainEntry = read('./main.tsx')
  const home = read('./ApplicationHome.tsx')
  const homeCss = read('./applicationHome.css')
  const literatureEntry = read('./literature/main.tsx')
  const literature = read('./literature/LiteratureApp.tsx')
  const literatureCss = read('./literature/styles.css')

  it('passes the resolved stored appearance into the feature hub and literature surface', () => {
    expect(mainEntry).toContain('resolveTheme(')
    expect(mainEntry).toMatch(/<ApplicationHome[\s\S]*themeId=/)
    expect(mainEntry).toMatch(/<ApplicationHome[\s\S]*customSkin=/)
    expect(literatureEntry).toContain('resolveTheme(')
    expect(literatureEntry).toMatch(/<LiteratureApp[\s\S]*themeId=/)
    expect(literatureEntry).toMatch(/<LiteratureApp[\s\S]*customSkin=/)
  })

  it('mounts the shared SkinChrome instead of a surface-specific HUD copy', () => {
    expect(home).toContain("import { SkinChrome } from './SkinChrome'")
    expect(home).toContain('<SkinChrome')
    expect(home).toContain('hud-layout')
    expect(literature).toContain("import { SkinChrome } from '../SkinChrome'")
    expect(literature).toContain('<SkinChrome')
    expect(literature).toContain('hud-layout')
  })

  it('defines Neon structural layouts for both non-workbench surfaces', () => {
    expect(homeCss).toContain(':root[data-theme="neon-space-lab"] .mode-hub-shell.hud-layout')
    expect(homeCss).toContain(':root[data-theme="neon-space-lab"] .mode-card')
    expect(literatureCss).toContain(':root[data-theme="neon-space-lab"] .app-shell.hud-layout')
    expect(literatureCss).toContain(':root[data-theme="neon-space-lab"] .library-panel')
    expect(literatureCss).toContain(':root[data-theme="neon-space-lab"] .message-bubble')
  })
})
