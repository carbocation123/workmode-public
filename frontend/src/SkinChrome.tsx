import { NeonHud } from './NeonHud'
import type { CustomSkinState } from './customSkin'
import type { ThemeId } from './theme'
import type { ReactNode } from 'react'

export interface SkinRuntimeProps {
  projectName?: string
  projectPath?: string
  modelName?: string
  streaming: boolean
  status: string
}

interface SkinChromeProps extends SkinRuntimeProps {
  themeId: ThemeId
  customSkin?: CustomSkinState | null
}

type SkinChromeRenderer = (props: SkinRuntimeProps) => ReactNode

const SKIN_CHROME_REGISTRY: Partial<Record<ThemeId, SkinChromeRenderer>> = {
  'neon-space-lab': (props) => <NeonHud {...props} />
}

export function SkinChrome({ themeId, customSkin, ...runtimeProps }: SkinChromeProps) {
  if (customSkin?.enabled && customSkin.skin.chrome?.type === 'hud') {
    return <NeonHud {...runtimeProps} chrome={customSkin.skin.chrome} />
  }
  return SKIN_CHROME_REGISTRY[themeId]?.(runtimeProps) ?? null
}
