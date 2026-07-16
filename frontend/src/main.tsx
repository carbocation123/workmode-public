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
import {
  generateDesktopBugReport,
  initializeDesktop,
  isDesktopApp,
  logDesktopFrontendEvent,
} from './desktop'
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

function frontendErrorText(value: unknown) {
  if (value instanceof Error) return `${value.name}: ${value.message}\n${value.stack || ''}`
  return String(value)
}

if (isDesktopApp()) {
  window.addEventListener('error', (event) => {
    void logDesktopFrontendEvent('error', 'window_error', frontendErrorText(event.error || event.message)).catch(() => undefined)
  })
  window.addEventListener('unhandledrejection', (event) => {
    void logDesktopFrontendEvent('error', 'unhandled_rejection', frontendErrorText(event.reason)).catch(() => undefined)
  })
}
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
    const startupError = frontendErrorText(error)
    void logDesktopFrontendEvent('error', 'desktop_startup', startupError).catch(() => undefined)
    root.render(
      <div className="desktop-startup-error">
        <h1>Workmode Public 启动失败</h1>
        <p>{error instanceof Error ? error.message : String(error)}</p>
        <p>可以生成本次启动的脱敏错误报告；文件管理器会自动定位 ZIP。</p>
        <button
          type="button"
          onClick={async (event) => {
            const button = event.currentTarget
            button.disabled = true
            button.textContent = '正在生成……'
            try {
              const bundle = await generateDesktopBugReport(`# Workmode Public 启动失败\n\n${startupError}`)
              button.textContent = bundle ? `已生成 ${bundle.fileName}` : '仅桌面版支持生成 ZIP'
            } catch (reportError) {
              button.textContent = `生成失败：${reportError instanceof Error ? reportError.message : String(reportError)}`
              button.disabled = false
            }
          }}
        >
          一键生成错误报告
        </button>
      </div>
    )
  }
}

bootstrap()
