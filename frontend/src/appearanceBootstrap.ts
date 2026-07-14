import {
  CUSTOM_SKIN_STORAGE_KEY,
  applyCustomSkinToRoot,
  getActiveCustomSkin,
  getSkinFoundationTheme,
  parseCustomSkinLibraryState,
  type ActiveCustomSkin,
  type CustomSkinLibraryState,
} from './customSkin'
import { ONBOARDING_STORAGE_KEY, parseProgress } from './onboarding'
import {
  THEME_STORAGE_KEY,
  allowedThemeSelection,
  applyThemeToRoot,
  parseThemePreference,
  type ThemePreference,
} from './theme'

export interface StoredAppearance {
  library: CustomSkinLibraryState
  activeSkin: ActiveCustomSkin | null
  theme: ThemePreference
}

export function readStoredAppearance(storage: Pick<Storage, 'getItem'>): StoredAppearance {
  const library = parseCustomSkinLibraryState(storage.getItem(CUSTOM_SKIN_STORAGE_KEY))
  let activeSkin = getActiveCustomSkin(library)
  const theme = parseThemePreference(storage.getItem(THEME_STORAGE_KEY))
  if (activeSkin?.enabled) theme.selection = getSkinFoundationTheme(activeSkin.skin)
  theme.selection = allowedThemeSelection(
    theme.selection,
    parseProgress(storage.getItem(ONBOARDING_STORAGE_KEY)).achievements,
  )
  if (activeSkin?.enabled && theme.selection !== getSkinFoundationTheme(activeSkin.skin)) {
    activeSkin = null
  }
  return { library, activeSkin, theme }
}

export function applyStoredAppearance(
  root: HTMLElement,
  appearance: StoredAppearance,
  prefersDark: boolean,
) {
  applyThemeToRoot(root, appearance.theme, prefersDark)
  applyCustomSkinToRoot(root, appearance.activeSkin)
}

export function disableStoredActiveSkin(storage: Pick<Storage, 'setItem'>, appearance: StoredAppearance) {
  if (!appearance.activeSkin) return
  storage.setItem(CUSTOM_SKIN_STORAGE_KEY, JSON.stringify({
    ...appearance.library,
    activeSkinId: null,
  }))
}
