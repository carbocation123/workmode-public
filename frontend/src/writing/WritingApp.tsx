import { useCallback, useEffect, useMemo, useState } from 'react'

import { skinUsesChrome, type ActiveCustomSkin } from '../customSkin'
import { applicationHomeUrl, workbenchSettingsUrl } from '../literatureNavigation'
import { SkinChrome } from '../SkinChrome'
import { THEMES, type ThemeId } from '../theme'
import {
  historyDate,
  historyPreview,
  historySummary,
  modeLabel,
  sortHistory,
  type DeletedWritingHistory,
  type WritingHistoryRecord,
  type WritingHistorySummary,
  type WritingMode,
} from './model'
import {
  deleteHistory,
  getWritingStatus,
  listHistory,
  listTrash,
  loadHistoryRecord,
  processText,
  restoreHistory,
  type WritingStatus,
} from './writingApi'


interface WritingAppProps {
  themeId: ThemeId
  customSkin: ActiveCustomSkin | null
}


export default function WritingApp({ themeId, customSkin }: WritingAppProps) {
  const [status, setStatus] = useState<WritingStatus | null>(null)
  const [history, setHistory] = useState<WritingHistorySummary[]>([])
  const [trash, setTrash] = useState<DeletedWritingHistory[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [mode, setMode] = useState<WritingMode>('polish')
  const [inputText, setInputText] = useState('')
  const [outputText, setOutputText] = useState('')
  const [loading, setLoading] = useState(true)
  const [processing, setProcessing] = useState(false)
  const [showTrash, setShowTrash] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const hudLayoutActive = Boolean(customSkin?.enabled && skinUsesChrome(customSkin.skin))
    || THEMES.some((theme) => theme.id === themeId && theme.layout === 'hud')

  const selectedRecord = useMemo(
    () => history.find((item) => item.id === selectedId) || null,
    [history, selectedId],
  )

  const refreshLists = useCallback(async () => {
    const [items, deleted] = await Promise.all([listHistory(), listTrash()])
    setHistory(sortHistory(items))
    setTrash(deleted)
  }, [])

  useEffect(() => {
    void Promise.all([getWritingStatus(), listHistory(), listTrash()])
      .then(([nextStatus, items, deleted]) => {
        setStatus(nextStatus)
        setHistory(sortHistory(items))
        setTrash(deleted)
      })
      .catch((reason) => setError(`文章处理状态读取失败：${reason instanceof Error ? reason.message : String(reason)}`))
      .finally(() => setLoading(false))
  }, [])

  async function openHistory(recordId: string) {
    setError('')
    setNotice('')
    try {
      const record = await loadHistoryRecord(recordId)
      setSelectedId(record.id)
      setMode(record.mode)
      setInputText(record.input_text)
      setOutputText(record.output_text)
    } catch (reason) {
      setError(`历史记录读取失败：${reason instanceof Error ? reason.message : String(reason)}`)
    }
  }

  async function runProcessing() {
    if (processing || !inputText.trim()) return
    setProcessing(true)
    setError('')
    setNotice('')
    try {
      const record = await processText(mode, inputText)
      setHistory((current) => sortHistory([historySummary(record), ...current.filter((item) => item.id !== record.id)]))
      setSelectedId(record.id)
      setOutputText(record.output_text)
      setNotice('处理完成，已保存到本地历史')
    } catch (reason) {
      setError(`处理失败：${reason instanceof Error ? reason.message : String(reason)}`)
    } finally {
      setProcessing(false)
    }
  }

  async function removeHistory(recordId: string) {
    if (!window.confirm('删除这条处理历史？删除后可以在“已删除记录”中恢复。')) return
    setError('')
    setNotice('')
    try {
      await deleteHistory(recordId)
      if (selectedId === recordId) setSelectedId(null)
      await refreshLists()
      setNotice('历史记录已移入已删除记录')
    } catch (reason) {
      setError(`删除失败：${reason instanceof Error ? reason.message : String(reason)}`)
    }
  }

  async function restoreDeleted(item: DeletedWritingHistory) {
    setError('')
    setNotice('')
    try {
      const restored = await restoreHistory(item.trash_id)
      await refreshLists()
      setShowTrash(false)
      await openHistory(restored.id)
      setNotice('处理历史已恢复')
    } catch (reason) {
      setError(`恢复失败：${reason instanceof Error ? reason.message : String(reason)}`)
    }
  }

  async function copyOutput() {
    if (!outputText) return
    try {
      await navigator.clipboard.writeText(outputText)
      setNotice('结果已复制')
      setError('')
    } catch (reason) {
      setError(`复制失败：${reason instanceof Error ? reason.message : String(reason)}`)
    }
  }

  return (
    <main className={`writing-shell${hudLayoutActive ? ' hud-layout' : ''}`} data-skin-slot="app-shell">
      <div className="skin-background-layer" aria-hidden />
      <div className="skin-decoration-overlay" aria-hidden />
      {hudLayoutActive && (
        <SkinChrome
          themeId={themeId}
          customSkin={customSkin}
          projectName="文章处理"
          projectPath={status?.history_path || '本地处理历史'}
          modelName={status?.model_name || 'WORKMODE CORE'}
          streaming={processing}
          status={error ? 'ATTENTION' : processing ? 'PROCESSING' : loading ? 'SCANNING' : 'READY'}
        />
      )}

      <header className="writing-header" data-skin-slot="writing-header">
        <button type="button" className="writing-icon-button" onClick={() => window.location.assign(applicationHomeUrl(window.location.href))}>
          ← <span>功能大厅</span>
        </button>
        <div className="writing-title">
          <strong>文章处理</strong>
          <span>文字润色与文章内部漏洞核查</span>
        </div>
        <div className="writing-header-status">
          <span className={status?.model_api_configured ? 'ready' : 'warning'}>
            {status?.model_api_configured ? `模型：${status.model_name}` : '尚未配置模型'}
          </span>
          <button
            type="button"
            className="writing-icon-button"
            onClick={() => window.location.assign(workbenchSettingsUrl(window.location.href, 'writing'))}
          >
            ⚙ <span>模型设置</span>
          </button>
        </div>
      </header>

      <section className="writing-workspace">
        <aside className="writing-history" data-skin-slot="writing-history">
          <div className="writing-panel-heading">
            <div><strong>处理历史</strong><small>{history.length} 条记录</small></div>
            <button type="button" onClick={() => setShowTrash((value) => !value)}>
              已删除记录{trash.length ? ` ${trash.length}` : ''}
            </button>
          </div>

          {showTrash ? (
            <div className="writing-history-list" aria-label="已删除记录">
              {trash.length === 0 && <div className="writing-empty">暂无已删除记录</div>}
              {trash.map((item) => (
                <article className="writing-history-card deleted" key={item.trash_id}>
                  <strong>{modeLabel(item.record.mode)}</strong>
                  <p>{historyPreview(item.record.input_preview)}</p>
                  <small>{historyDate(item.deleted_at)}</small>
                  <button type="button" onClick={() => void restoreDeleted(item)}>恢复</button>
                </article>
              ))}
            </div>
          ) : (
            <div className="writing-history-list" aria-label="处理历史列表">
              {history.length === 0 && !loading && <div className="writing-empty">还没有处理历史<br />粘贴文字后开始第一次处理</div>}
              {history.map((item) => (
                <article
                  className={`writing-history-card${item.id === selectedId ? ' selected' : ''}`}
                  key={item.id}
                >
                  <button type="button" className="writing-history-open" onClick={() => void openHistory(item.id)}>
                    <span><strong>{modeLabel(item.mode)}</strong><small>{item.input_chars.toLocaleString()} 字</small></span>
                    <p>{historyPreview(item.input_preview)}</p>
                    <time>{historyDate(item.created_at)}</time>
                  </button>
                  <button
                    type="button"
                    className="writing-history-delete"
                    aria-label={`删除${historyPreview(item.input_preview, 12)}`}
                    onClick={() => void removeHistory(item.id)}
                  >
                    ×
                  </button>
                </article>
              ))}
            </div>
          )}
        </aside>

        <section className="writing-main" data-skin-slot="writing-main">
          <div className="writing-toolbar">
            <div className="writing-mode-picker" role="radiogroup" aria-label="处理功能">
              <button
                type="button"
                role="radio"
                aria-checked={mode === 'polish'}
                className={mode === 'polish' ? 'active' : ''}
                onClick={() => setMode('polish')}
              >
                <strong>文字润色</strong>
                <span>改善表达，保留事实与结论强度</span>
              </button>
              <button
                type="button"
                role="radio"
                aria-checked={mode === 'audit'}
                className={mode === 'audit' ? 'active' : ''}
                onClick={() => setMode('audit')}
              >
                <strong>查找漏洞</strong>
                <span>核查证据链、逻辑与表述一致性</span>
              </button>
            </div>
            <div className="writing-toolbar-actions">
              <span>自动使用 Unicode 上下标：H₂O · 10⁻³ · R²</span>
              {selectedRecord && (
                <button type="button" className="writing-secondary-button" disabled={processing} onClick={() => void runProcessing()}>
                  重新处理
                </button>
              )}
              <button
                type="button"
                className="writing-primary-button"
                disabled={processing || !inputText.trim()}
                onClick={() => void runProcessing()}
              >
                {processing ? '正在处理…' : '开始处理'}
              </button>
            </div>
          </div>

          <div className="writing-editor-grid">
            <label className="writing-editor-panel" data-skin-slot="writing-input">
              <span className="writing-editor-heading"><strong>文字输入</strong><small>{inputText.length.toLocaleString()} 字</small></span>
              <textarea
                value={inputText}
                maxLength={200000}
                placeholder={mode === 'polish'
                  ? '在这里粘贴需要润色的文字…'
                  : '在这里粘贴需要核查的文章。段落越完整，证据链和一致性核查越可靠…'}
                onChange={(event) => {
                  setInputText(event.target.value)
                  setSelectedId(null)
                }}
              />
            </label>

            <label className="writing-editor-panel" data-skin-slot="writing-output">
              <span className="writing-editor-heading">
                <strong>文字输出</strong>
                <span><small>{outputText.length.toLocaleString()} 字</small><button type="button" disabled={!outputText} onClick={() => void copyOutput()}>复制结果</button></span>
              </span>
              <textarea
                value={outputText}
                readOnly
                placeholder={mode === 'polish'
                  ? '润色后的文字会显示在这里。'
                  : '文章内部的证据链、逻辑和一致性问题会显示在这里。'}
              />
            </label>
          </div>
        </section>
      </section>

      <footer className="writing-footer">
        <span>处理成功后才写入本地历史 · 删除记录可恢复</span>
        <span>{notice || (error ? '' : '输入和输出不会进入 Workmode 会话')}</span>
      </footer>
      {error && <div className="writing-alert" role="alert">{error}</div>}
    </main>
  )
}
