import { describe, expect, it } from 'vitest'
import { SUPPORT_EMAIL, buildBugReport, buildSupportMailto } from './bugReport'

describe('quick bug report', () => {
  it('builds a useful diagnostic template without project or secret fields', () => {
    const report = buildBugReport({
      version: '0.6.4',
      runtime: 'desktop',
      platform: 'Windows x64',
      language: 'zh-CN',
      theme: 'lab',
      customSkin: 'pixel-night-shift'
    })

    expect(report).toContain('Workmode Public 0.6.4')
    expect(report).toContain('desktop')
    expect(report).toContain('pixel-night-shift')
    expect(report).toContain('问题描述')
    expect(report).toContain('复现步骤')
    expect(report).not.toMatch(/api.?key|项目路径|对话正文|root_path/i)
  })

  it('opens the fixed support mailbox with the report prefilled', () => {
    const report = 'Workmode Public 0.6.4\n请描述问题'
    const mailto = buildSupportMailto(report)

    expect(SUPPORT_EMAIL).toBe('yantianxue_skye@qq.com')
    expect(mailto).toMatch(/^mailto:yantianxue_skye%40qq\.com\?/)
    expect(decodeURIComponent(mailto)).toContain(report)
  })

  it('flattens untrusted runtime labels to one bounded line', () => {
    const report = buildBugReport({
      version: '0.6.4\nAPI_KEY=secret',
      runtime: 'desktop',
      platform: 'Windows\r\nD:\\private',
      language: 'zh-CN',
      theme: 'lab'
    })

    expect(report).not.toContain('API_KEY=secret')
    expect(report).not.toContain('D:\\private')
  })
})
