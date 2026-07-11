import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import { setApiBase } from './api'
import { initializeDesktop } from './desktop'
import { CUSTOM_SKIN_STORAGE_KEY, applyCustomSkinToRoot, parseCustomSkinState } from './customSkin'
import { ONBOARDING_STORAGE_KEY, parseProgress } from './onboarding'
import { THEME_STORAGE_KEY, allowedThemeSelection, applyThemeToRoot, parseThemePreference } from './theme'
import './styles.css'

let initialCustomSkin = parseCustomSkinState(localStorage.getItem(CUSTOM_SKIN_STORAGE_KEY))
const initialTheme = parseThemePreference(localStorage.getItem(THEME_STORAGE_KEY))
if (initialCustomSkin?.enabled) initialTheme.selection = initialCustomSkin.skin.baseTheme
initialTheme.selection = allowedThemeSelection(
  initialTheme.selection,
  parseProgress(localStorage.getItem(ONBOARDING_STORAGE_KEY)).achievements
)
if (initialCustomSkin?.enabled && initialTheme.selection !== initialCustomSkin.skin.baseTheme) {
  initialCustomSkin = { ...initialCustomSkin, enabled: false }
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
