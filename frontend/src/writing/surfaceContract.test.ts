import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

function read(relativePath: string): string {
  return new TextDecoder().decode(readFileSync(new URL(relativePath, import.meta.url)))
}

describe('article processing surface contract', () => {
  const app = read('./WritingApp.tsx')
  const home = read('../ApplicationHome.tsx')
  const vite = read('../../vite.config.ts')

  it('is registered as a sessionless application-home entry', () => {
    expect(vite).toContain("writing: 'writing/index.html'")
    expect(home).toContain('文章处理')
    expect(home).toContain('writingWorkbenchUrl')
    expect(app).not.toContain('createSession')
    expect(app).not.toContain('/sessions')
  })

  it('offers history, input, output and exactly two primary processing modes', () => {
    expect(app).toContain('处理历史')
    expect(app).toContain('文字输入')
    expect(app).toContain('文字输出')
    expect(app).toContain('文字润色')
    expect(app).toContain('查找漏洞')
    expect(app).toContain('开始处理')
    expect(app).toContain('复制结果')
  })

  it('loads immutable history and exposes recoverable deletion', () => {
    expect(app).toContain('loadHistoryRecord')
    expect(app).toContain('deleteHistory')
    expect(app).toContain('listTrash')
    expect(app).toContain('restoreHistory')
    expect(app).toContain('已删除记录')
    expect(app).toContain('重新处理')
  })

  it('describes real unicode scripts instead of marker syntax', () => {
    expect(app).toContain('H₂O')
    expect(app).toContain('10⁻³')
    expect(app).not.toContain('SUP:')
    expect(app).not.toContain('SUB:')
  })
})
