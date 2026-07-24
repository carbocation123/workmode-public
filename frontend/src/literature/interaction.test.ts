import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const source = new TextDecoder().decode(readFileSync(new URL('./LiteratureApp.tsx', import.meta.url)))
const styles = new TextDecoder().decode(readFileSync(new URL('./styles.css', import.meta.url)))
const appStyles = new TextDecoder().decode(readFileSync(new URL('../styles.css', import.meta.url)))
const onboarding = new TextDecoder().decode(readFileSync(new URL('../OnboardingUI.tsx', import.meta.url)))
const literatureOnboarding = new TextDecoder().decode(readFileSync(new URL('./LiteratureOnboarding.tsx', import.meta.url)))
const literatureApi = new TextDecoder().decode(readFileSync(new URL('./literatureApi.ts', import.meta.url)))
const desktop = new TextDecoder().decode(readFileSync(new URL('../desktop.ts', import.meta.url)))

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

  it('guides single-paper close reading toward evidence-based figure walkthroughs', () => {
    expect(source).toContain('选中一篇后说“精读这篇”，默认逐图讲解')
    expect(literatureOnboarding).toContain('精读这篇')
    expect(literatureOnboarding).toContain('默认逐图讲解')
    expect(literatureOnboarding).toContain('图表信息不足时会明确说明，不会猜测')
  })

  it('offers recoverable paper deletion and removes deleted papers from live attachments', () => {
    expect(source).toContain('文献回收站')
    expect(source).toContain('移入回收站')
    expect(source).toContain('attachedPaperIds: session.attachedPaperIds.filter')
    expect(source).toContain('restoreBackendPaper')
    expect(styles).toContain('.literature-trash-modal')
  })

  it('imports an EndNote library into the current project with plain-language safeguards', () => {
    expect(source).toContain('导入 EndNote 文献库')
    expect(source).toContain('合并到当前项目')
    expect(source).toContain('请先关闭 EndNote')
    expect(source).toContain('自动查找')
    expect(source).toContain('扫描本机所有磁盘')
    expect(source).toContain('可能需要几十秒')
    expect(source).toContain('手动选择')
    expect(source).toContain('导入完成后查重')
    expect(literatureApi).toContain('findEndNoteLibraries')
    expect(literatureApi).toContain('previewEndNoteLibrary')
    expect(literatureApi).toContain('importEndNoteLibrary')
    expect(literatureApi).toContain('scanBackendDuplicates')
    expect(desktop).toContain("extensions: ['enl', 'enlx']")
    expect(styles).toContain('.endnote-import-modal')
  })

  it('uses project tag groups and exposes each paper SI folder', () => {
    expect(source).not.toContain('const TAG_CATEGORIES')
    expect(source).toContain('tagGroups')
    expect(source).toContain('打开 SI 文件夹')
    expect(literatureApi).toContain('openBackendSiFolder')
  })

  it('shows and searches the same useful bibliographic and workflow fields exposed to AI', () => {
    expect(source).toContain('paper.doi')
    expect(source).toContain('<strong>期刊</strong>')
    expect(source).toContain('<strong>DOI</strong>')
    expect(source).toContain('<strong>第一作者姓</strong>')
    expect(source).toContain('<strong>期刊缩写</strong>')
    expect(source).toContain('<strong>处理阶段</strong>')
    expect(source).toContain('<strong>处理错误</strong>')
    expect(source).toContain('<strong>SI 文件夹</strong>')
  })

  it('uses one compact library toolbar instead of unrelated stacked controls', () => {
    expect(source).toContain('className="library-panel-header"')
    expect(source).toContain('className="library-project-selector"')
    expect(source).toContain('className="library-command-row"')
    expect(source).toContain('className="library-import-menu"')
    expect(source).toContain('导入 PDF')
    expect(source).toContain('导入 EndNote')
    expect(source).toContain('管理项目')
    expect(source).toContain('文献回收站')
    expect(source).not.toContain('<span className="eyebrow">LIBRARY</span>')
    expect(source).not.toContain('<h1>文献库</h1>')
    expect(source).not.toContain('className="endnote-import-trigger"')
    expect(styles).toContain('.library-command-row')
    expect(styles).toContain('--library-control-height: 34px')
  })

  it('renders dense paper cards without repeating filenames', () => {
    expect(source).not.toContain('<p className="paper-filename">{paper.filename}</p>')
    expect(source).not.toContain('<p className="original-filename">标准名：{paper.archiveFilename}</p>')
    expect(source).toContain('paper.groupIds.slice(0, 1)')
    expect(source).toContain('paper.tagIds.slice(0, 3)')
    expect(source).not.toContain('className="library-footnote"')
    expect(styles).toContain('padding: 10px 11px')
    expect(styles).toContain('.paper-card-meta')
  })
})
