import { useRef, useState } from 'react'
import {
  getSkinChromePreset,
  getSkinFoundationTheme,
  getActiveCustomSkin,
  isV3Skin,
  isSupportedSkinFilename,
  removeCustomSkinFromLibrary,
  upsertOfficialSkins,
  type CustomSkinLibraryState
} from './customSkin'
import { removeSkinAssets, replaceOfficialSkinAssets } from './skinAssetStore'
import { parseSkinImportFile } from './skinPackage'
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
  customSkinLibrary: CustomSkinLibraryState
  onCustomSkinLibraryChange: (state: CustomSkinLibraryState) => void
}

export function ThemePanel({
  preference,
  achievements,
  systemPrefersDark,
  onChange,
  customSkinLibrary,
  onCustomSkinLibraryChange
}: ThemePanelProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [skinStatus, setSkinStatus] = useState('')
  const customSkin = getActiveCustomSkin(customSkinLibrary)

  function skinSummary() {
    if (!customSkin) return ''
    const { skin } = customSkin
    if (isV3Skin(skin)) {
      return `${skin.id} · v${skin.version} · ${skin.material.preset} · ${skin.components.chrome} · ${skin.icons.preset}`
    }
    return `${skin.id} · v${skin.version} · 基于 ${THEMES.find((theme) => theme.id === skin.baseTheme)?.name}${skin.chrome ? ' · HUD' : ''}${skin.material ? ` · ${skin.material.preset}` : ''}`
  }

  function select(selection: ThemeSelection) {
    if (customSkinLibrary.activeSkinId) {
      onCustomSkinLibraryChange({ ...customSkinLibrary, activeSkinId: null })
    }
    onChange({ ...preference, selection })
  }

  async function importSkins(files: FileList | null) {
    const selectedFiles = Array.from(files || [])
    if (!selectedFiles.length) return
    try {
      const imports = []
      for (const file of selectedFiles) {
        if (!isSupportedSkinFilename(file.name)) throw new Error(`「${file.name}」只接受官方签名的 .workmode-skin 文件`)
        const parsed = await parseSkinImportFile(file)
        const base = THEMES.find((theme) => theme.id === getSkinFoundationTheme(parsed.skin))
        if (!base || !themeIsUnlocked(base, achievements)) throw new Error(base?.unlockHint || '基础主题不可用')
        imports.push(parsed)
      }
      for (const entry of imports) await replaceOfficialSkinAssets(entry.skin.id, entry.assets, entry.styles)
      const skins = imports.map((entry) => entry.skin)
      const nextLibrary = upsertOfficialSkins(customSkinLibrary, imports)
      const activeSkin = skins[skins.length - 1]
      onCustomSkinLibraryChange(nextLibrary)
      onChange({ ...preference, selection: getSkinFoundationTheme(activeSkin) })
      setSkinStatus(skins.length === 1
        ? `已导入并启用「${activeSkin.name}」`
        : `已导入 ${skins.length} 个皮肤，并启用「${activeSkin.name}」`)
    } catch (error) {
      setSkinStatus(error instanceof Error ? error.message : String(error))
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  function activateCustomSkin(skinId: string) {
    if (!skinId) {
      onCustomSkinLibraryChange({ ...customSkinLibrary, activeSkinId: null })
      setSkinStatus('已停用本地皮肤；皮肤库仍保留')
      return
    }
    const skin = customSkinLibrary.skins.find((candidate) => candidate.id === skinId)
    if (!skin) return
    const baseTheme = getSkinFoundationTheme(skin)
    const base = THEMES.find((theme) => theme.id === baseTheme)
    if (!base || !themeIsUnlocked(base, achievements)) {
      setSkinStatus(base?.unlockHint || '基础主题不可用')
      return
    }
    onChange({ ...preference, selection: baseTheme })
    onCustomSkinLibraryChange({ ...customSkinLibrary, activeSkinId: skin.id })
    setSkinStatus(`已启用「${skin.name}」`)
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
            <strong>官方签名皮肤</strong>
            <small>只接受经过 Workmode 官方 Ed25519 签名的 .workmode-skin；签名覆盖布局 CSS、视觉 CSS、字体、图标和图片，文件被修改后会立即拒绝。</small>
          </div>
          <button type="button" className="project-create-submit" onClick={() => fileInputRef.current?.click()}>导入皮肤</button>
          <input
            ref={fileInputRef}
            className="custom-skin-file-input"
            type="file"
            multiple
            accept=".workmode-skin,application/zip"
            onChange={(event) => importSkins(event.target.files)}
          />
        </div>
        {customSkinLibrary.skins.length > 0 && (
          <div className="custom-skin-library-controls">
            <label htmlFor="custom-skin-select">可用 {customSkinLibrary.skins.length} 个</label>
            <select
              id="custom-skin-select"
              className="custom-skin-select"
              value={customSkinLibrary.activeSkinId || ''}
              onChange={(event) => activateCustomSkin(event.target.value)}
            >
              <option value="">不使用本地皮肤</option>
              {customSkinLibrary.skins.map((skin) => (
                <option key={skin.id} value={skin.id}>{skin.name} · v{skin.version}</option>
              ))}
            </select>
          </div>
        )}
        {customSkin && (
          <div className={customSkin.enabled ? 'custom-skin-card enabled' : 'custom-skin-card'}>
            <span className="theme-card-icon">◈</span>
            <span className="custom-skin-card-copy">
              <strong>{customSkin.skin.name}</strong>
              <small>{skinSummary()}{getSkinChromePreset(customSkin.skin) !== 'none' ? ' · 结构外壳' : ''}</small>
            </span>
            <span className="custom-skin-state">{customSkin.enabled ? '已启用' : '已停用'}</span>
            <button
              type="button"
              className="project-create-cancel"
              onClick={() => activateCustomSkin('')}
            >
              停用
            </button>
            <button
              type="button"
              className="project-create-cancel"
              onClick={() => {
                onCustomSkinLibraryChange(removeCustomSkinFromLibrary(customSkinLibrary, customSkin.skin.id))
                setSkinStatus(`已从皮肤库移除「${customSkin.skin.name}」`)
                void removeSkinAssets(customSkin.skin.id).catch((error) => {
                  setSkinStatus(`声明已移除，但资源清理失败：${error instanceof Error ? error.message : String(error)}`)
                })
              }}
            >移除</button>
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
