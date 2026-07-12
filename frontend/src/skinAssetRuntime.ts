import { loadSkinAssets, SKIN_LAYOUT_ASSET_ID, SKIN_VISUAL_ASSET_ID } from './skinAssetStore'
import { isV3Skin, skinIconDatasetKey, type ActiveCustomSkin, type SkinFontRole, type SkinIconSlot } from './skinProtocol'

const FONT_VARIABLES: Record<SkinFontRole, string> = {
  ui: '--skin-font-ui',
  content: '--skin-font-content',
  code: '--skin-font-code',
  display: '--skin-font-display'
}

let runtimeGeneration = 0
let activeCleanup: (() => void) | null = null

function cssUrl(url: string) {
  return `url("${url.replace(/["\\]/g, '')}")`
}

export async function refreshSkinAssetRuntime(root: HTMLElement, state: ActiveCustomSkin | null) {
  runtimeGeneration += 1
  const generation = runtimeGeneration
  activeCleanup?.()
  activeCleanup = null
  if (!state || !isV3Skin(state.skin)) return

  const assets = await loadSkinAssets(state.skin.id)
  if (generation !== runtimeGeneration) return
  const objectUrls: string[] = []
  const fonts: FontFace[] = []
  const properties: string[] = []
  const datasetKeys: string[] = []
  let officialStyle: HTMLStyleElement | null = null
  const cleanup = () => {
    properties.forEach((property) => root.style.removeProperty(property))
    datasetKeys.forEach((key) => delete root.dataset[key])
    objectUrls.forEach((url) => URL.revokeObjectURL(url))
    fonts.forEach((font) => document.fonts.delete(font))
    officialStyle?.remove()
  }

  const assetUrls = new Map<string, string>()
  const assetUrl = (assetId: string) => {
    const existing = assetUrls.get(assetId)
    if (existing) return existing
    const blob = assets.get(assetId)
    if (!blob) return null
    const url = URL.createObjectURL(blob)
    objectUrls.push(url)
    assetUrls.set(assetId, url)
    return url
  }

  const layoutStylesheet = assets.get(SKIN_LAYOUT_ASSET_ID)
  const visualStylesheet = assets.get(SKIN_VISUAL_ASSET_ID)
  if (!layoutStylesheet || !visualStylesheet || typeof document === 'undefined') {
    cleanup()
    throw new Error('官方皮肤缺少已验证的 layout.css 或 visual.css')
  }
  const rewriteAssetUrls = (css: string) => css.replace(
    /workmode-asset:\/\/([A-Za-z0-9._-]{1,48})/g,
    (source, assetId: string) => assetUrl(assetId) || source
  )
  officialStyle = document.createElement('style')
  officialStyle.dataset.workmodeOfficialSkin = state.skin.id
  officialStyle.textContent = `${rewriteAssetUrls(await layoutStylesheet.text())}\n${rewriteAssetUrls(await visualStylesheet.text())}`
  document.head.appendChild(officialStyle)

  if (state.skin.background) {
    const url = assetUrl(state.skin.background.asset)
    if (url) {
      root.style.setProperty('--skin-background-image', cssUrl(url))
      properties.push('--skin-background-image')
      root.dataset.skinHasBackground = 'true'
      datasetKeys.push('skinHasBackground')
    }
  }

  if (state.skin.decoration.overlay) {
    const url = assetUrl(state.skin.decoration.overlay.asset)
    if (url) {
      root.style.setProperty('--skin-decoration-overlay-image', cssUrl(url))
      properties.push('--skin-decoration-overlay-image')
      root.dataset.skinHasDecorationOverlay = 'true'
      datasetKeys.push('skinHasDecorationOverlay')
    }
  }

  Object.entries(state.skin.icons.overrides || {}).forEach(([slot, assetId]) => {
    const url = assetUrl(assetId)
    if (!url) return
    const property = `--skin-icon-${slot as SkinIconSlot}`
    root.style.setProperty(property, cssUrl(url))
    properties.push(property)
    const datasetKey = skinIconDatasetKey(slot as SkinIconSlot)
    root.dataset[datasetKey] = 'asset'
    datasetKeys.push(datasetKey)
    root.dataset.skinHasIconAssets = 'true'
    if (!datasetKeys.includes('skinHasIconAssets')) datasetKeys.push('skinHasIconAssets')
  })

  try {
    if (typeof FontFace !== 'undefined' && typeof document !== 'undefined') {
      await Promise.all(Object.entries(state.skin.typography.assets || {}).map(async ([role, assetId]) => {
        const url = assetUrl(assetId)
        if (!url) return
        const family = `WorkmodeSkin-${state.skin.id}-${role}`
        const font = new FontFace(family, cssUrl(url), { display: 'swap' })
        await font.load()
        if (generation !== runtimeGeneration) return
        document.fonts.add(font)
        fonts.push(font)
        const property = FONT_VARIABLES[role as SkinFontRole]
        root.style.setProperty(property, `"${family}"`)
        properties.push(property)
      }))
    }
  } catch (error) {
    cleanup()
    throw error
  }

  if (generation !== runtimeGeneration) {
    cleanup()
    return
  }
  activeCleanup = cleanup
}
