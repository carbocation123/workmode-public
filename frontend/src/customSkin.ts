export * from './skinLibrary'
export * from './skinProtocol'

import { CUSTOM_SKIN_MANIFEST_MAX_BYTES } from './skinProtocol'

/** Kept for protocol parser tests; production import accepts signed packages only. */
export const CUSTOM_SKIN_MAX_BYTES = CUSTOM_SKIN_MANIFEST_MAX_BYTES

export function isSupportedSkinFilename(name: string) {
  return name.toLowerCase().endsWith('.workmode-skin')
}

export function isSkinPackageFilename(name: string) {
  return name.toLowerCase().endsWith('.workmode-skin')
}
