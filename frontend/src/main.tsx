import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import ApplicationHome from './ApplicationHome'
import { setApiBase } from './api'
import {
  applyStoredAppearance,
  disableStoredActiveSkin,
  readStoredAppearance,
} from './appearanceBootstrap'
import { initializeDesktop } from './desktop'
import {
  CUSTOM_SKIN_STORAGE_KEY,
  LEGACY_CUSTOM_SKIN_STORAGE_KEY,
  SKIN_RUNTIME_GUARD_KEY,
  parseCustomSkinLibraryState
} from './customSkin'
import { removeLegacySkinAssetDatabase } from './skinAssetStore'
import { refreshSkinAssetRuntime } from './skinAssetRuntime'
import { resolveApplicationSurface } from './literatureNavigation'
import { ensureDevelopmentAchievements } from './onboarding'
import { resolveTheme } from './theme'
import './styles.css'
import './themeContract.css'
import './skinRuntime.css'
import './applicationHome.css'

localStorage.removeItem(LEGACY_CUSTOM_SKIN_STORAGE_KEY)
removeLegacySkinAssetDatabase()
let initialCustomSkinLibrary = parseCustomSkinLibraryState(localStorage.getItem(CUSTOM_SKIN_STORAGE_KEY))
const guardedSkinId = localStorage.getItem(SKIN_RUNTIME_GUARD_KEY)
if (guardedSkinId && initialCustomSkinLibrary.activeSkinId === guardedSkinId) {
  initialCustomSkinLibrary = { ...initialCustomSkinLibrary, activeSkinId: null }
  localStorage.setItem(CUSTOM_SKIN_STORAGE_KEY, JSON.stringify(initialCustomSkinLibrary))
}
localStorage.removeItem(SKIN_RUNTIME_GUARD_KEY)
const unlockSourceAchievements = import.meta.env.DEV
  || import.meta.env.VITE_WORKMODE_SOURCE_ACHIEVEMENTS === '1'
ensureDevelopmentAchievements(localStorage, unlockSourceAchievements)

window.addEventListener('keydown', (event) => {
  if (!(event.ctrlKey && event.altKey && event.shiftKey && event.key.toLowerCase() === 'r')) return
  event.preventDefault()
  localStorage.removeItem(CUSTOM_SKIN_STORAGE_KEY)
  localStorage.removeItem(LEGACY_CUSTOM_SKIN_STORAGE_KEY)
  localStorage.removeItem(SKIN_RUNTIME_GUARD_KEY)
  window.location.reload()
})
const initialAppearance = readStoredAppearance(localStorage)
const prefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? true
applyStoredAppearance(document.documentElement, initialAppearance, prefersDark)
const initialThemeId = resolveTheme(initialAppearance.theme.selection, prefersDark)
const initialSurface = resolveApplicationSurface(window.location.href)
if (initialSurface === 'home') {
  void refreshSkinAssetRuntime(document.documentElement, initialAppearance.activeSkin).catch(() => {
    disableStoredActiveSkin(localStorage, initialAppearance)
    const fallbackAppearance = readStoredAppearance(localStorage)
    applyStoredAppearance(document.documentElement, fallbackAppearance, prefersDark)
    return refreshSkinAssetRuntime(document.documentElement, null)
  })
}

async function bootstrap() {
  const root = ReactDOM.createRoot(document.getElementById('root')!)
  try {
    const desktop = await initializeDesktop()
    if (desktop) setApiBase(desktop.apiBase)
    root.render(
      <React.StrictMode>
        {initialSurface === 'workbench'
          ? <App />
          : <ApplicationHome themeId={initialThemeId} customSkin={initialAppearance.activeSkin} />}
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
