import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const app = new TextDecoder().decode(readFileSync(new URL('./App.tsx', import.meta.url)))
const styles = new TextDecoder().decode(readFileSync(new URL('./styles.css', import.meta.url)))

describe('settings layout', () => {
  it('uses a balanced two-column card system with full-width feature sections', () => {
    expect(styles).toContain('grid-template-columns: repeat(2, minmax(320px, 1fr))')
    expect(styles).toContain('.settings-open .settings-section-theme,')
    expect(styles).toContain('.settings-open .settings-section-memory')
    expect(styles).toContain('align-items: stretch')
  })

  it('keeps feedback inside the application and support card', () => {
    expect(app).toContain('settings-section-support settings-section-desktop')
    expect(app).toContain('settings-support-content')
    expect(app).not.toContain('<section className="settings-section settings-section-support">')
  })
})
