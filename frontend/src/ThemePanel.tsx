import {
  THEMES,
  type ThemePreference,
  type ThemeSelection,
  themeIsUnlocked
} from './theme'

interface ThemePanelProps {
  preference: ThemePreference
  achievements: Record<string, string>
  systemPrefersDark: boolean
  onChange: (preference: ThemePreference) => void
}

export function ThemePanel({ preference, achievements, systemPrefersDark, onChange }: ThemePanelProps) {
  function select(selection: ThemeSelection) {
    onChange({ ...preference, selection })
  }

  return (
    <div className="theme-panel">
      <p className="settings-hint">即时预览，只保存在本机，不进入项目和模型上下文。</p>
      <div className="theme-grid">
        <button
          type="button"
          className={preference.selection === 'system' ? 'theme-card selected' : 'theme-card'}
          aria-pressed={preference.selection === 'system'}
          onClick={() => select('system')}
        >
          <span className="theme-card-icon">◒</span>
          <span className="theme-card-copy"><strong>跟随系统</strong><small>当前将使用{systemPrefersDark ? '深夜观测站' : '论文纸'}</small></span>
          <span className="theme-swatches" aria-hidden><i style={{ background: '#f3efe6' }} /><i style={{ background: '#12162a' }} /><i style={{ background: '#6c9fff' }} /></span>
        </button>
        {THEMES.map((theme) => {
          const unlocked = themeIsUnlocked(theme, achievements)
          const selected = preference.selection === theme.id
          return (
            <button
              type="button"
              key={theme.id}
              className={`${selected ? 'theme-card selected' : 'theme-card'}${unlocked ? '' : ' locked'}`}
              aria-pressed={selected}
              disabled={!unlocked}
              title={unlocked ? theme.description : theme.unlockHint}
              onClick={() => select(theme.id)}
            >
              <span className="theme-card-icon">{unlocked ? theme.icon : '◇'}</span>
              <span className="theme-card-copy"><strong>{theme.name}</strong><small>{unlocked ? theme.description : theme.unlockHint}</small></span>
              <span className="theme-swatches" aria-hidden>{theme.swatches.map((color) => <i key={color} style={{ background: color }} />)}</span>
            </button>
          )
        })}
      </div>
      <label className="settings-toggle theme-motion-toggle">
        <input
          type="checkbox"
          checked={preference.reduceMotion}
          onChange={(event) => onChange({ ...preference, reduceMotion: event.target.checked })}
        />
        降低动效
      </label>
    </div>
  )
}
