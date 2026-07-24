import { NeonHud } from './NeonHud'
import { getSkinChromePreset, isLegacySkin, type ActiveCustomSkin } from './customSkin'
import { PresetChrome } from './PresetChrome'
import type { ThemeId } from './theme'
import type { ReactNode } from 'react'

export interface SkinRuntimeProps {
  projectName?: string
  projectPath?: string
  modelName?: string
  streaming: boolean
  status: string
  actions?: ReactNode
}

interface SkinChromeProps extends SkinRuntimeProps {
  themeId: ThemeId
  customSkin?: ActiveCustomSkin | null
}

type SkinChromeRenderer = (props: SkinRuntimeProps) => ReactNode

const SKIN_CHROME_REGISTRY: Partial<Record<ThemeId, SkinChromeRenderer>> = {
  'neon-space-lab': (props) => <NeonHud {...props} />
}

export function SkinChrome({ themeId, customSkin, ...runtimeProps }: SkinChromeProps) {
  if (customSkin?.enabled) {
    const preset = getSkinChromePreset(customSkin.skin)
    if (preset === 'hud') {
      const legacyChrome = isLegacySkin(customSkin.skin) ? customSkin.skin.chrome : undefined
      return <NeonHud {...runtimeProps} chrome={legacyChrome} />
    }
    if (preset === 'terminal' || preset === 'observatory' || preset === 'console' || preset === 'gem-tech') {
      return <PresetChrome {...runtimeProps} preset={preset} />
    }
  }
  return SKIN_CHROME_REGISTRY[themeId]?.(runtimeProps) ?? null
}
