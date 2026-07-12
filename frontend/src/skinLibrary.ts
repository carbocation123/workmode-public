import { parseDeclarativeSkin, type ActiveCustomSkin, type DeclarativeSkin } from './skinProtocol'
import type { OfficialSkinTrust, ParsedSkinImport } from './skinPackage'

export const CUSTOM_SKIN_STORAGE_KEY = 'workmode-public-official-skins-v1'
export const LEGACY_CUSTOM_SKIN_STORAGE_KEY = 'workmode-public-custom-skin-v1'
export const SKIN_RUNTIME_GUARD_KEY = 'workmode-public-official-skin-boot-guard-v1'

export interface LegacyCustomSkinState {
  version: 1
  enabled: boolean
  skin: DeclarativeSkin
}

export interface CustomSkinLibraryState {
  version: 4
  activeSkinId: string | null
  skins: DeclarativeSkin[]
  receipts: Record<string, OfficialSkinTrust>
}

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

export function parseCustomSkinState(raw: string | null): LegacyCustomSkinState | null {
  if (!raw) return null
  try {
    const parsed = JSON.parse(raw) as unknown
    if (!isObject(parsed) || parsed.version !== 1 || typeof parsed.enabled !== 'boolean') return null
    return {
      version: 1,
      enabled: parsed.enabled,
      skin: parseDeclarativeSkin(JSON.stringify(parsed.skin))
    }
  } catch {
    return null
  }
}

export function parseCustomSkinLibraryState(raw: string | null): CustomSkinLibraryState {
  const empty: CustomSkinLibraryState = { version: 4, activeSkinId: null, skins: [], receipts: {} }
  if (!raw) return empty
  try {
    const persisted = JSON.parse(raw) as unknown
    if (!isObject(persisted) || persisted.version !== 4 || !Array.isArray(persisted.skins) || !isObject(persisted.receipts)) return empty
    const persistedReceipts = persisted.receipts
    const skinsById = new Map<string, DeclarativeSkin>()
    const receipts: Record<string, OfficialSkinTrust> = {}
    persisted.skins.forEach((candidate) => {
      try {
        const skin = parseDeclarativeSkin(JSON.stringify(candidate))
        const receipt = persistedReceipts[skin.id]
        if (!isObject(receipt) || typeof receipt.keyId !== 'string' || !/^[A-Za-z0-9._-]{1,64}$/.test(receipt.keyId)
          || typeof receipt.packageDigest !== 'string' || !/^[a-f0-9]{64}$/.test(receipt.packageDigest)) return
        skinsById.set(skin.id, skin)
        receipts[skin.id] = { keyId: receipt.keyId, packageDigest: receipt.packageDigest }
      } catch {
        // Keep valid entries when one locally stored declaration is damaged.
      }
    })
    const skins = Array.from(skinsById.values())
    const activeSkinId = typeof persisted.activeSkinId === 'string'
      && skins.some((skin) => skin.id === persisted.activeSkinId)
      ? persisted.activeSkinId
      : null
    return { version: 4, activeSkinId, skins, receipts }
  } catch {
    return empty
  }
}

export function getActiveCustomSkin(library: CustomSkinLibraryState): ActiveCustomSkin | null {
  if (!library.activeSkinId) return null
  const skin = library.skins.find((candidate) => candidate.id === library.activeSkinId)
  return skin && library.receipts[skin.id] ? { enabled: true, skin } : null
}

export function upsertOfficialSkins(
  library: CustomSkinLibraryState,
  imports: ParsedSkinImport[]
): CustomSkinLibraryState {
  if (!imports.length) return library
  const skins = [...library.skins]
  const receipts = { ...library.receipts }
  imports.forEach(({ skin, trust }) => {
    const existingIndex = skins.findIndex((candidate) => candidate.id === skin.id)
    if (existingIndex >= 0) skins[existingIndex] = skin
    else skins.push(skin)
    receipts[skin.id] = trust
  })
  return {
    version: 4,
    activeSkinId: imports[imports.length - 1].skin.id,
    skins,
    receipts
  }
}

export function removeCustomSkinFromLibrary(
  library: CustomSkinLibraryState,
  skinId: string
): CustomSkinLibraryState {
  const receipts = { ...library.receipts }
  delete receipts[skinId]
  return {
    version: 4,
    activeSkinId: library.activeSkinId === skinId ? null : library.activeSkinId,
    skins: library.skins.filter((skin) => skin.id !== skinId),
    receipts
  }
}
