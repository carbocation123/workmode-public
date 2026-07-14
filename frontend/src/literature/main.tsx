import React from 'react'
import ReactDOM from 'react-dom/client'

import {
  applyStoredAppearance,
  disableStoredActiveSkin,
  readStoredAppearance,
} from '../appearanceBootstrap'
import { refreshSkinAssetRuntime } from '../skinAssetRuntime'
import { ensureDevelopmentAchievements } from '../onboarding'
import { resolveTheme } from '../theme'
import LiteratureApp from './LiteratureApp'
import '../styles.css'
import '../themeContract.css'
import '../skinRuntime.css'
import './styles.css'

const unlockSourceAchievements = import.meta.env.DEV
  || import.meta.env.VITE_WORKMODE_SOURCE_ACHIEVEMENTS === '1'
ensureDevelopmentAchievements(localStorage, unlockSourceAchievements)
const appearance = readStoredAppearance(localStorage)
const prefersDark = window.matchMedia?.('(prefers-color-scheme: dark)').matches ?? true
applyStoredAppearance(document.documentElement, appearance, prefersDark)
const themeId = resolveTheme(appearance.theme.selection, prefersDark)
void refreshSkinAssetRuntime(document.documentElement, appearance.activeSkin).catch(() => {
  disableStoredActiveSkin(localStorage, appearance)
  const fallbackAppearance = readStoredAppearance(localStorage)
  applyStoredAppearance(document.documentElement, fallbackAppearance, prefersDark)
  return refreshSkinAssetRuntime(document.documentElement, null)
})

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <LiteratureApp themeId={themeId} customSkin={appearance.activeSkin} />
  </React.StrictMode>,
)
