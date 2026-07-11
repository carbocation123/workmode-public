import { useRef, useState } from 'react'
import {
  CUSTOM_SKIN_MAX_BYTES,
  isSupportedSkinFilename,
  parseDeclarativeSkin,
  type CustomSkinState
} from './customSkin'
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
  customSkin: CustomSkinState | null
  onCustomSkinChange: (state: CustomSkinState | null) => void
}

export function ThemePanel({
  preference,
  achievements,
  systemPrefersDark,
  onChange,
  customSkin,
  onCustomSkinChange
}: ThemePanelProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [skinStatus, setSkinStatus] = useState('')

  function select(selection: ThemeSelection) {
    if (customSkin?.enabled) onCustomSkinChange({ ...customSkin, enabled: false })
    onChange({ ...preference, selection })
  }

  async function importSkin(file: File | undefined) {
    if (!file) return
    try {
      if (!isSupportedSkinFilename(file.name)) throw new Error('皮肤文件必须使用 .json 扩展名')
      if (file.size > CUSTOM_SKIN_MAX_BYTES) throw new Error('皮肤文件不能超过 32 KB')
      const skin = parseDeclarativeSkin(await file.text())
      const base = THEMES.find((theme) => theme.id === skin.baseTheme)
      if (!base || !themeIsUnlocked(base, achievements)) throw new Error(base?.unlockHint || '基础主题不可用')
      onCustomSkinChange({ version: 1, enabled: true, skin })
      onChange({ ...preference, selection: skin.baseTheme })
      setSkinStatus(`已导入并启用「${skin.name}」`)
    } catch (error) {
      setSkinStatus(error instanceof Error ? error.message : String(error))
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  function enableCustomSkin() {
    if (!customSkin) return
    const base = THEMES.find((theme) => theme.id === customSkin.skin.baseTheme)
    if (!base || !themeIsUnlocked(base, achievements)) {
      setSkinStatus(base?.unlockHint || '基础主题不可用')
      return
    }
    onChange({ ...preference, selection: customSkin.skin.baseTheme })
    onCustomSkinChange({ ...customSkin, enabled: true })
    setSkinStatus(`已启用「${customSkin.skin.name}」`)
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
      <section className="custom-skin-loader">
        <div className="custom-skin-loader-head">
          <div>
            <strong>本地声明式皮肤</strong>
            <small>支持白名单视觉参数和 HUD 结构预设，不加载 CSS、脚本、网络资源或工具权限。</small>
          </div>
          <button type="button" className="project-create-submit" onClick={() => fileInputRef.current?.click()}>导入皮肤</button>
          <input
            ref={fileInputRef}
            className="custom-skin-file-input"
            type="file"
            accept=".json,.workmode-skin.json,application/json"
            onChange={(event) => importSkin(event.target.files?.[0])}
          />
        </div>
        {customSkin && (
          <div className={customSkin.enabled ? 'custom-skin-card enabled' : 'custom-skin-card'}>
            <span className="theme-card-icon">◈</span>
            <span className="custom-skin-card-copy">
              <strong>{customSkin.skin.name}</strong>
              <small>{customSkin.skin.id} · v{customSkin.skin.version} · 基于 {THEMES.find((theme) => theme.id === customSkin.skin.baseTheme)?.name}{customSkin.skin.chrome ? ' · HUD' : ''}</small>
            </span>
            <span className="custom-skin-state">{customSkin.enabled ? '已启用' : '已停用'}</span>
            <button
              type="button"
              className="project-create-cancel"
              onClick={() => customSkin.enabled
                ? onCustomSkinChange({ ...customSkin, enabled: false })
                : enableCustomSkin()}
            >
              {customSkin.enabled ? '停用' : '启用'}
            </button>
            <button
              type="button"
              className="project-create-cancel"
              onClick={() => {
                onCustomSkinChange(null)
                setSkinStatus('已卸载本地皮肤')
              }}
            >卸载</button>
          </div>
        )}
        {skinStatus && <div className="custom-skin-status">{skinStatus}</div>}
      </section>
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
