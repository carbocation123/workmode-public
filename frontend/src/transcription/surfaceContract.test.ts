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

  it('offers a replayable four-step guide without writing guide state into the workspace', () => {
    expect(app).toContain('<TranscriptionOnboarding')
    expect(app).toContain('使用指引')
    expect(onboarding).toContain('先配置 DashScope')
    expect(onboarding).toContain('批量上传录音')
    expect(onboarding).toContain('查看、整理与导出')
    expect(onboarding).toContain('可选：AI 润色与总结')
    expect(onboarding).toContain('先决定是否需要 AI')
    expect(onboarding).toContain('测试成功后保存')
    expect(onboarding).toContain('401/认证失败')
    expect(onboarding).toContain('每次都要在费用与隐私提示中再次确认')
    expect(onboarding).toContain('AI 出错不会修改原始 ASR')
    expect(onboarding).toContain('role="dialog"')
    expect(workbench).toContain('重新播放会议转写引导')
    expect(onboarding).not.toContain('/api/transcription')
  })

  it('manually generates clearable AI derivatives without replacing the ASR transcript', () => {
    expect(app).toContain('AI 润色')
    expect(app).toContain('AI 总结')
    expect(app).toContain('重新生成润色')
    expect(app).toContain('重新生成总结')
    expect(app).toContain('清除润色')
    expect(app).toContain('清除总结')
    expect(app).toContain('会把当前转写文本发送给你配置的模型服务')
    expect(app).toContain('可能产生费用')
    expect(app).toContain('不会覆盖原始转写')
    expect(app).toContain("transcriptFileUrl(selectedJob.id, 'polished')")
    expect(app).toContain("transcriptFileUrl(selectedJob.id, 'summary')")
  })

  it('explains DashScope signup as a foolproof, official-link workflow', () => {
    expect(onboarding).toContain('打开百炼控制台')
    expect(onboarding).toContain('登录或注册阿里云账号')
    expect(onboarding).toContain('实名认证')
    expect(onboarding).toContain('华北2（北京）')
    expect(onboarding).toContain('阅读并同意协议')
    expect(onboarding).toContain('默认业务空间')
    expect(onboarding).toContain('权限选择“全部”')
    expect(onboarding).toContain('立刻复制')
    expect(onboarding).toContain('按量付费')
    expect(onboarding).toContain('免费额度用完即停')
    expect(onboarding).toContain('查看阿里云官方步骤')
    expect(onboarding).toContain('openExternalUrl')
  })
})
