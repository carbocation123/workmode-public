import { useEffect, useState } from 'react'

import {
  checkForDesktopUpdateOnStartup,
  installDesktopUpdate,
  type DesktopUpdateInfo,
} from './desktop'
import './startupUpdatePrompt.css'

export function StartupUpdatePrompt() {
  const [update, setUpdate] = useState<DesktopUpdateInfo | null>(null)
  const [dismissed, setDismissed] = useState(false)
  const [installing, setInstalling] = useState(false)
  const [progress, setProgress] = useState<number | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let mounted = true
    void checkForDesktopUpdateOnStartup().then((availableUpdate) => {
      if (mounted && availableUpdate) setUpdate(availableUpdate)
    })
    return () => {
      mounted = false
    }
  }, [])

  if (!update || dismissed) return null

  async function installUpdate() {
    setInstalling(true)
    setError('')
    try {
      await installDesktopUpdate((downloaded, total) => {
        setProgress(total && total > 0 ? Math.min(100, Math.round((downloaded / total) * 100)) : null)
      })
    } catch (reason) {
      setInstalling(false)
      setError(reason instanceof Error ? reason.message : String(reason))
    }
  }

  return (
    <div className="startup-update-backdrop">
      <section
        className="startup-update-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="startup-update-title"
        aria-describedby="startup-update-description"
      >
        <span className="startup-update-eyebrow">WORKMODE UPDATE</span>
        <h2 id="startup-update-title">检测到新版本</h2>
        <p id="startup-update-description">
          Workmode Public {update.version} 已可用，是否现在更新？
        </p>
        {installing && (
          <p className="startup-update-progress" role="status">
            {progress === null ? '正在下载并安装更新…' : `正在下载并安装更新… ${progress}%`}
          </p>
        )}
        {error && <p className="startup-update-error" role="alert">更新失败：{error}</p>}
        <div className="startup-update-actions">
          <button type="button" onClick={() => setDismissed(true)} disabled={installing}>
            暂不更新
          </button>
          <button
            type="button"
            className="primary"
            onClick={() => void installUpdate()}
            disabled={installing}
          >
            {installing ? '正在更新…' : '立即更新'}
          </button>
        </div>
      </section>
    </div>
  )
}
