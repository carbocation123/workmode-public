import { useState } from 'react'
import supportQr from './assets/support-public-account-qr.jpg'
import { buildSupportMailto, SUPPORT_EMAIL } from './bugReport'
import { openExternalUrl } from './desktop'

interface BugReportDialogProps {
  report: string
  onClose: () => void
}

async function copyText(value: string) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value)
    return
  }
  const textarea = document.createElement('textarea')
  textarea.value = value
  textarea.style.position = 'fixed'
  textarea.style.opacity = '0'
  document.body.appendChild(textarea)
  textarea.select()
  const copied = document.execCommand('copy')
  textarea.remove()
  if (!copied) throw new Error('当前系统不允许自动复制')
}

export function BugReportDialog({ report, onClose }: BugReportDialogProps) {
  const [status, setStatus] = useState('')

  async function copyReport() {
    try {
      await copyText(report)
      setStatus('诊断信息已复制；发消息时再附上截图和复现步骤。')
    } catch (error) {
      setStatus(error instanceof Error ? error.message : String(error))
    }
  }

  async function sendEmail() {
    try {
      await openExternalUrl(buildSupportMailto(report))
      setStatus('已打开默认邮件客户端。')
    } catch (error) {
      setStatus(`无法打开邮件客户端：${error instanceof Error ? error.message : String(error)}`)
    }
  }

  return (
    <div className="bug-report-backdrop" role="presentation" onMouseDown={onClose}>
      <section className="bug-report-dialog" role="dialog" aria-modal="true" aria-labelledby="bug-report-title" onMouseDown={(event) => event.stopPropagation()}>
        <button type="button" className="bug-report-close" onClick={onClose} aria-label="关闭">×</button>
        <div className="bug-report-copy">
          <small>WORKMODE SUPPORT</small>
          <h2 id="bug-report-title">快速反馈 Bug</h2>
          <p>扫码关注“研天雪”公众号后私信，发送问题描述、截图和诊断信息；也可以直接发邮件。</p>
          <div className="bug-report-actions">
            <button type="button" className="project-create-submit" onClick={copyReport}>复制诊断信息</button>
            <button type="button" className="project-create-cancel" onClick={sendEmail}>发送邮件</button>
          </div>
          <a className="bug-report-email" href={buildSupportMailto(report)} onClick={(event) => { event.preventDefault(); sendEmail() }}>{SUPPORT_EMAIL}</a>
          {status && <div className="bug-report-status" role="status">{status}</div>}
          <details className="bug-report-preview">
            <summary>查看将复制的诊断模板</summary>
            <pre>{report}</pre>
          </details>
        </div>
        <figure className="bug-report-qr">
          <img src={supportQr} alt="研天雪公众号二维码" />
          <figcaption>关注公众号后私信反馈</figcaption>
        </figure>
      </section>
    </div>
  )
}
