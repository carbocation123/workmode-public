import { NeonHud } from './NeonHud'
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
}

type SkinChromeRenderer = (props: SkinRuntimeProps) => ReactNode

const SKIN_CHROME_REGISTRY: Partial<Record<ThemeId, SkinChromeRenderer>> = {
  'neon-space-lab': (props) => <NeonHud {...props} />
}

export function SkinChrome({ themeId, ...runtimeProps }: SkinChromeProps) {
  return SKIN_CHROME_REGISTRY[themeId]?.(runtimeProps) ?? null
}
