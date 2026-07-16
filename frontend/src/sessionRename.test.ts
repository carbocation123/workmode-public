import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const workbenchSource = new TextDecoder().decode(readFileSync(new URL('./App.tsx', import.meta.url)))
const workbenchStyles = new TextDecoder().decode(readFileSync(new URL('./styles.css', import.meta.url)))
const literatureSource = new TextDecoder().decode(readFileSync(new URL('./literature/LiteratureApp.tsx', import.meta.url)))
const literatureApiSource = new TextDecoder().decode(readFileSync(new URL('./literature/literatureApi.ts', import.meta.url)))
const literatureStyles = new TextDecoder().decode(readFileSync(new URL('./literature/styles.css', import.meta.url)))

describe('session rename contracts', () => {
  it('keeps the workbench rename action discoverable and keyboard accessible', () => {
    expect(workbenchSource).toContain('aria-label="重命名会话"')
    expect(workbenchSource).toContain('onDoubleClick={() => startRenamingSession(session)}')
    expect(workbenchSource).toContain("if (event.key === 'Enter')")
    expect(workbenchSource).toContain("if (event.key === 'Escape')")
    expect(workbenchStyles).toMatch(/\.session-row-actions\s*\{[^}]*opacity:\s*\.65/s)
  })

  it('renames the active literature session through the shared backend endpoint', () => {
    expect(literatureApiSource).toContain('export async function renameBackendSession')
    expect(literatureApiSource).toContain('api.updateSession(sessionId, title)')
    expect(literatureSource).toContain('renameBackendSession,')
    expect(literatureSource).toContain('async function renameActiveSession')
    expect(literatureSource).toContain('aria-label="重命名当前会话"')
    expect(literatureSource).toContain('aria-labelledby="rename-session-title"')
    expect(literatureSource).toContain('data-skin-slot="session-rename"')
    expect(literatureSource).toContain('maxLength={80}')
    expect(literatureStyles).toContain('.session-rename-modal')
  })
})
