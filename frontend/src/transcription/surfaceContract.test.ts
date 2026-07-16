import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

function read(relativePath: string): string {
  return new TextDecoder().decode(readFileSync(new URL(relativePath, import.meta.url)))
}

describe('meeting transcription surface contract', () => {
  const app = read('./TranscriptionApp.tsx')
  const onboarding = read('./TranscriptionOnboarding.tsx')
  const home = read('../ApplicationHome.tsx')
  const workbench = read('../App.tsx')
  const vite = read('../../vite.config.ts')

  it('is registered as a third multi-page feature-hub entry', () => {
    expect(vite).toContain("transcription: 'transcription/index.html'")
    expect(home).toContain('会议录音转文字')
    expect(home).toContain('transcriptionWorkbenchUrl')
  })

  it('accepts multiple audio files and exposes list, transcript, retry and delete controls', () => {
    expect(app).toMatch(/type="file"[\s\S]*multiple/)
    expect(app).toContain('转写记录')
    expect(app).toContain('重新转写')
    expect(app).toContain('删除记录')
    expect(app).toContain('打开输出文件夹')
  })

  it('does not create or read Workmode sessions', () => {
    expect(app).not.toContain('createSession')
    expect(app).not.toContain('sessionId')
    expect(app).not.toContain('/sessions')
  })

  it('offers a replayable three-step guide without writing guide state into the workspace', () => {
    expect(app).toContain('<TranscriptionOnboarding')
    expect(app).toContain('使用指引')
    expect(onboarding).toContain('先配置 DashScope')
    expect(onboarding).toContain('批量上传录音')
    expect(onboarding).toContain('查看、整理与导出')
    expect(onboarding).toContain('role="dialog"')
    expect(workbench).toContain('重新播放会议转写引导')
    expect(onboarding).not.toContain('/api/transcription')
  })
})
