import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const source = new TextDecoder().decode(readFileSync(new URL('./LiteratureApp.tsx', import.meta.url)))
const styles = new TextDecoder().decode(readFileSync(new URL('./styles.css', import.meta.url)))
const appStyles = new TextDecoder().decode(readFileSync(new URL('../styles.css', import.meta.url)))
const onboarding = new TextDecoder().decode(readFileSync(new URL('../OnboardingUI.tsx', import.meta.url)))
const literatureOnboarding = new TextDecoder().decode(readFileSync(new URL('./LiteratureOnboarding.tsx', import.meta.url)))

describe('literature live interaction contracts', () => {
  it('uses VS Code-style follow-latest behavior instead of forcing every delta into view', () => {
    expect(source).toContain('messageStreamRef')
    expect(source).toContain('followingLatestRef')
    expect(source).toContain('isNearBottom')
    expect(source).toContain('showBackToLatest')
    expect(source).toContain('onScroll={handleMessageStreamScroll}')
    expect(source).toContain('回到最新 ↓')
    expect(source).not.toContain('chatEndRef.current?.scrollIntoView')
    expect(styles).toContain('.literature-back-to-latest')
  })

  it('refreshes real changed paths even when a batch tool only partially succeeds', () => {
    expect(source).toContain("event.type === 'tool_result'")
    expect(source).toContain('scheduleProjectionRefresh(changedPaths)')
    expect(source).not.toContain("event.type === 'tool_result' && event.ok !== false")
  })

  it('lays out settings as compact responsive cards and keeps exact setup guidance', () => {
    expect(appStyles).toContain('grid-template-columns: repeat(2, minmax(320px, 1fr))')
    expect(onboarding).toContain('点击「创建 API Key」')
    expect(onboarding).toContain('复制新生成的 Key')
    expect(literatureOnboarding).toContain('MinerU')
    expect(literatureOnboarding).toContain('设置')
  })

  it('shows actionable metadata review state instead of hiding partial pipeline success', () => {
    expect(source).toContain('detailPaper.metadataTrust !== \'complete\'')
    expect(source).toContain('metadata-review-notice')
    expect(source).toContain('元数据待人工确认')
    expect(styles).toContain('.metadata-review-notice')
  })

  it('keeps confirmed imports lightweight until the user explicitly selects or processes them', () => {
    expect(source).not.toContain('attachedPaperIds: attachPapers(session.attachedPaperIds, uniqueImportedIds)')
    expect(source).not.toContain('<span>{statusLabel(paper.status)}</span>')
    expect(source).not.toContain("paper.archiveLocation.replace('文献/', '')")
    expect(source).not.toContain("paper.archiveFilename ?? '标准命名待确认'")
    expect(source).not.toContain("paper.year ?? '年份待识别'")
    expect(source).toContain('PDF 只会加入文献库，不会自动解析或加入当前对话')
  })

  it('treats MinerU as an optional advanced feature in the beginner guide', () => {
    expect(literatureOnboarding).toContain('需要更精确地识别表格、公式或复杂版面时')
    expect(literatureOnboarding).toContain('设置中配置 MinerU')
    expect(literatureOnboarding).not.toContain('创建并复制 Token')
  })

  it('offers recoverable paper deletion and removes deleted papers from live attachments', () => {
    expect(source).toContain('文献回收站')
    expect(source).toContain('移入回收站')
    expect(source).toContain('attachedPaperIds: session.attachedPaperIds.filter')
    expect(source).toContain('restoreBackendPaper')
    expect(styles).toContain('.literature-trash-modal')
  })
})
