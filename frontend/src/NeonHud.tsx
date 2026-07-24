import { useEffect, useState } from 'react'
import type { DeclarativeHudChrome } from './customSkin'
import type { SkinRuntimeProps } from './SkinChrome'

function formatClock(date: Date) {
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}

interface NeonHudProps extends SkinRuntimeProps {
  chrome?: DeclarativeHudChrome
}

export function NeonHud({ projectName, projectPath, modelName, streaming, status, actions, chrome }: NeonHudProps) {
  const [now, setNow] = useState(() => new Date())

  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(timer)
  }, [])

  return (
    <header className="neon-hud" data-skin-slot="app-chrome" aria-label={`${chrome?.title || 'Neon Space Lab'} 舰桥状态栏`}>
      <span className="neon-hud-rail rail-primary" aria-hidden />
      <span className="neon-hud-rail rail-secondary" aria-hidden />
      <div className="neon-brand">
        <span className="neon-brand-ring" aria-hidden />
        <span className="neon-brand-copy"><strong>{chrome?.title || 'WORKMODE'}</strong><small>{chrome?.subtitle || 'NEON SPACE LAB'}</small></span>
      </div>
      <div className="neon-mission">
        <span>{chrome?.missionLabel || 'ACTIVE MISSION'}</span>
        <strong>{projectName || 'NO PROJECT LINKED'}</strong>
        <small>{projectPath || 'SELECT A LOCAL RESEARCH WORKSPACE'}</small>
      </div>
      <div className="neon-telemetry">
        <span><small>{chrome?.modelLabel || 'MODEL LINK'}</small><strong>{modelName || 'NOT CONFIGURED'}</strong></span>
        <span><small>{chrome?.stateLabel || 'CORE STATE'}</small><strong className={streaming ? 'live' : ''}>{streaming ? 'GENERATING' : status || 'READY'}</strong></span>
        <span><small>{chrome?.timeLabel || 'LOCAL TIME'}</small><strong>{formatClock(now)}</strong></span>
        {actions && <div className="skin-chrome-actions">{actions}</div>}
      </div>
    </header>
  )
}
