import { useEffect, useState } from 'react'
import type { V3ChromePreset } from './customSkin'
import type { SkinRuntimeProps } from './SkinChrome'

interface PresetChromeProps extends SkinRuntimeProps {
  preset: Extract<V3ChromePreset, 'terminal' | 'observatory' | 'console' | 'gem-tech'>
}

const CHROME_COPY: Record<PresetChromeProps['preset'], {
  ariaLabel: string
  emblem: string
  title: string
  projectLabel: string
  modelLabel: string
  stateLabel: string
}> = {
  terminal: {
    ariaLabel: '终端状态栏', emblem: 'W>', title: 'WORKMODE TERMINAL',
    projectLabel: 'PROJECT', modelLabel: 'MODEL', stateLabel: 'STATE'
  },
  observatory: {
    ariaLabel: '星象塔状态栏', emblem: '✦', title: '紫晶星象塔',
    projectLabel: '研究典藏', modelLabel: '演算核心', stateLabel: '观测状态'
  },
  console: {
    ariaLabel: '控制台状态栏', emblem: '◉', title: 'WORKMODE CONSOLE',
    projectLabel: 'ACTIVE PROJECT', modelLabel: 'MODEL CHANNEL', stateLabel: 'RUN STATE'
  },
  'gem-tech': {
    ariaLabel: '宝石机能状态栏', emblem: '◆', title: 'CRYSTAL WORKBENCH',
    projectLabel: 'PROJECT', modelLabel: 'REASONING CORE', stateLabel: 'CORE STATE'
  }
}

export function PresetChrome({ preset, projectName, projectPath, modelName, streaming, status, actions, onProjectClick, projectGuideTarget }: PresetChromeProps) {
  const [now, setNow] = useState(() => new Date())
  useEffect(() => {
    const timer = window.setInterval(() => setNow(new Date()), 1000)
    return () => window.clearInterval(timer)
  }, [])
  const copy = CHROME_COPY[preset]
  return (
    <header className={`preset-chrome preset-chrome-${preset}`} data-skin-slot="app-chrome" aria-label={copy.ariaLabel}>
      <span className="preset-chrome-emblem" aria-hidden>{copy.emblem}</span>
      <span className="preset-chrome-brand"><strong>{copy.title}</strong><small>{projectPath || 'SELECT A LOCAL RESEARCH WORKSPACE'}</small></span>
      {onProjectClick ? (
        <button className="preset-chrome-field preset-chrome-project" data-literature-guide={projectGuideTarget} type="button" onClick={onProjectClick} title="管理项目">
          <small>{copy.projectLabel}</small><strong>{projectName || 'NO PROJECT'}</strong>
        </button>
      ) : (
        <span className="preset-chrome-field"><small>{copy.projectLabel}</small><strong>{projectName || 'NO PROJECT'}</strong></span>
      )}
      <span className="preset-chrome-field"><small>{copy.modelLabel}</small><strong>{modelName || 'NOT CONFIGURED'}</strong></span>
      <span className="preset-chrome-field"><small>{copy.stateLabel}</small><strong className={streaming ? 'live' : ''}>{streaming ? 'GENERATING' : status || 'READY'}</strong></span>
      <span className="preset-chrome-clock">{now.toLocaleTimeString('zh-CN', { hour12: false })}</span>
      {actions && <div className="skin-chrome-actions">{actions}</div>}
    </header>
  )
}
