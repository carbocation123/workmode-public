import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { setApiBase } from './api'
import { initializeDesktop } from './desktop'
import {
  CUSTOM_SKIN_STORAGE_KEY,
  LEGACY_CUSTOM_SKIN_STORAGE_KEY,
  SKIN_RUNTIME_GUARD_KEY,
  applyCustomSkinToRoot,
  getActiveCustomSkin,
  getSkinFoundationTheme,
  parseCustomSkinLibraryState
} from './customSkin'
import { removeLegacySkinAssetDatabase } from './skinAssetStore'
import { ONBOARDING_STORAGE_KEY, parseProgress } from './onboarding'
import { THEME_STORAGE_KEY, allowedThemeSelection, applyThemeToRoot, parseThemePreference } from './theme'
import './styles.css'
import './skinRuntime.css'

localStorage.removeItem(LEGACY_CUSTOM_SKIN_STORAGE_KEY)
removeLegacySkinAssetDatabase()
let initialCustomSkinLibrary = parseCustomSkinLibraryState(localStorage.getItem(CUSTOM_SKIN_STORAGE_KEY))
const guardedSkinId = localStorage.getItem(SKIN_RUNTIME_GUARD_KEY)
if (guardedSkinId && initialCustomSkinLibrary.activeSkinId === guardedSkinId) {
  initialCustomSkinLibrary = { ...initialCustomSkinLibrary, activeSkinId: null }
  localStorage.setItem(CUSTOM_SKIN_STORAGE_KEY, JSON.stringify(initialCustomSkinLibrary))
}
localStorage.removeItem(SKIN_RUNTIME_GUARD_KEY)

window.addEventListener('keydown', (event) => {
  if (!(event.ctrlKey && event.altKey && event.shiftKey && event.key.toLowerCase() === 'r')) return
  event.preventDefault()
  localStorage.removeItem(CUSTOM_SKIN_STORAGE_KEY)
  localStorage.removeItem(LEGACY_CUSTOM_SKIN_STORAGE_KEY)
  localStorage.removeItem(SKIN_RUNTIME_GUARD_KEY)
  window.location.reload()
})
let initialCustomSkin = getActiveCustomSkin(initialCustomSkinLibrary)
const initialTheme = parseThemePreference(localStorage.getItem(THEME_STORAGE_KEY))
if (initialCustomSkin?.enabled) initialTheme.selection = getSkinFoundationTheme(initialCustomSkin.skin)
initialTheme.selection = allowedThemeSelection(
  initialTheme.selection,
  parseProgress(localStorage.getItem(ONBOARDING_STORAGE_KEY)).achievements
)
if (initialCustomSkin?.enabled && initialTheme.selection !== getSkinFoundationTheme(initialCustomSkin.skin)) {
  initialCustomSkin = null
}
applyThemeToRoot(document.documentElement, initialTheme, window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? true)
applyCustomSkinToRoot(document.documentElement, initialCustomSkin)

async function bootstrap() {
  const root = ReactDOM.createRoot(document.getElementById('root')!)
  try {
    const desktop = await initializeDesktop()
    if (desktop) setApiBase(desktop.apiBase)
    root.render(
      <React.StrictMode>
        <App />
      </React.StrictMode>
    )
  } catch (error) {
    root.render(
      <div className="desktop-startup-error">
        <h1>Workmode Public 启动失败</h1>
        <p>{error instanceof Error ? error.message : String(error)}</p>
        <p>请重新启动应用；详细信息位于用户数据目录的 logs 文件夹。</p>
      </div>
    )
  }
}

bootstrap()
