export const SUPPORT_EMAIL = 'yantianxue_skye@qq.com'

export interface BugReportContext {
  version: string
  runtime: 'desktop' | 'web'
  platform: string
  language: string
  theme: string
  customSkin?: string | null
}

function safeLine(value: string | null | undefined, fallback: string) {
  const firstLine = String(value || '').split(/[\r\n]/, 1)[0]
  const cleaned = firstLine.replace(/[\u0000-\u001f\u007f]/g, '').trim().slice(0, 180)
  return cleaned || fallback
}

export function buildBugReport(context: BugReportContext) {
  const version = safeLine(context.version, 'unknown')
  const runtime = context.runtime === 'desktop' ? 'desktop' : 'web'
  const platform = safeLine(context.platform, 'unknown')
  const language = safeLine(context.language, 'unknown')
  const theme = safeLine(context.theme, 'unknown')
  const customSkin = safeLine(context.customSkin, 'none')

  return [
    `# Workmode Public ${version} Bug 快速报告`,
    '',
    '## 问题描述',
    '请说明发生了什么：',
    '',
    '## 复现步骤',
    '1. ',
    '2. ',
    '3. ',
    '',
    '## 预期结果',
    '',
    '## 实际结果',
    '',
    '## 自动诊断',
    `- 版本：${version}`,
    `- 运行环境：${runtime}`,
    `- 平台：${platform}`,
    `- 界面语言：${language}`,
    `- 当前主题：${theme}`,
    `- 本地皮肤：${customSkin}`,
    `- 生成时间：${new Date().toISOString()}`,
    '',
    '> 请附上相关截图。自动诊断仅包含应用与界面环境信息，不包含用户内容或本地目录。'
  ].join('\n')
}

export function buildSupportMailto(report: string) {
  const subject = 'Workmode Public Bug 报告'
  return `mailto:${encodeURIComponent(SUPPORT_EMAIL)}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(report)}`
}
