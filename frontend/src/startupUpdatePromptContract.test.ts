import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

function read(relativePath: string): string {
  return new TextDecoder().decode(readFileSync(new URL(relativePath, import.meta.url)))
}

describe('shared startup update prompt', () => {
  const mainEntry = read('./main.tsx')
  const prompt = read('./StartupUpdatePrompt.tsx')

  it('mounts once above every application surface', () => {
    expect(mainEntry).toContain("import { StartupUpdatePrompt } from './StartupUpdatePrompt'")
    expect(mainEntry).toContain('<StartupUpdatePrompt />')
  })

  it('asks before installing an update found during startup', () => {
    expect(prompt).toContain('checkForDesktopUpdateOnStartup')
    expect(prompt).toContain('检测到新版本')
    expect(prompt).toContain('是否现在更新？')
    expect(prompt).toContain('installDesktopUpdate')
    expect(prompt).toContain('role="dialog"')
    expect(prompt).toContain('暂不更新')
    expect(prompt).toContain('立即更新')
  })
})
