import { useEffect, useState } from 'react'
import type { SkinRuntimeProps } from './SkinChrome'

function formatClock(date: Date) {
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}

export function NeonHud({ projectName, projectPath, modelName, streaming, status }: SkinRuntimeProps) {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  return (
    <header className="neon-hud" aria-label="Neon Space Lab 舰桥状态栏">
      <span className="neon-hud-rail rail-primary" aria-hidden />
      <span className="neon-hud-rail rail-secondary" aria-hidden />
      <div className="neon-brand">
        <span className="neon-brand-ring" aria-hidden />
        <span className="neon-brand-copy"><strong>WORKMODE</strong><small>NEON SPACE LAB</small></span>
      </div>
      <div className="neon-mission">
        <span>ACTIVE MISSION</span>
        <strong>{projectName || 'NO PROJECT LINKED'}</strong>
        <small>{projectPath || 'SELECT A LOCAL RESEARCH WORKSPACE'}</small>
      </div>
      <div className="neon-telemetry">
        <span><small>MODEL LINK</small><strong>{modelName || 'NOT CONFIGURED'}</strong></span>
        <span><small>CORE STATE</small><strong className={streaming ? 'live' : ''}>{streaming ? 'GENERATING' : status || 'READY'}</strong></span>
        <span><small>LOCAL TIME</small><strong>{formatClock(now)}</strong></span>
      </div>
    </header>
  )
}
