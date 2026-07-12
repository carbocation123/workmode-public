import { afterEach, describe, expect, it, vi } from 'vitest'

const store = vi.hoisted(() => ({ loadSkinAssets: vi.fn() }))
vi.mock('./skinAssetStore', () => ({
  loadSkinAssets: store.loadSkinAssets,
  SKIN_LAYOUT_ASSET_ID: '__official_layout_css__',
  SKIN_VISUAL_ASSET_ID: '__official_visual_css__'
}))

import { isLegacySkin, parseDeclarativeSkin } from './customSkin'
import { refreshSkinAssetRuntime } from './skinAssetRuntime'
import { SKIN_LAYOUT_ASSET_ID, SKIN_VISUAL_ASSET_ID } from './skinAssetStore'

function rootElement() {
  const properties = new Map<string, string>()
  const root = {
    dataset: {} as Record<string, string>,
    style: {
      setProperty: (key: string, value: string) => properties.set(key, value),
      removeProperty: (key: string) => properties.delete(key)
    }
  } as unknown as HTMLElement
  return { root, properties }
}

function overlaySkin() {
  const skin = parseDeclarativeSkin(JSON.stringify({
    schema: 'workmode-skin/v3',
    id: 'overlay-test',
    name: 'Overlay Test',
    version: '3.0.0',
    foundation: 'dark',
    palette: { accent: '#66ccff' },
    typography: { preset: 'system' },
    material: { preset: 'flat' },
    geometry: {},
    components: { chrome: 'none', messages: 'bubbles', tools: 'card', context: 'bar', fileTree: 'standard' },
    icons: { preset: 'default' },
    effects: { preset: 'none' },
    decoration: { preset: 'none', overlay: { asset: 'overlay', fit: 'contain', position: 'right', opacity: 0.3 } },
    assets: [{ id: 'overlay', path: 'decorations/overlay.png', kind: 'image' }]
  }))
  if (isLegacySkin(skin)) throw new Error('Expected a v3 skin')
  return skin
}

afterEach(() => {
  vi.unstubAllGlobals()
  store.loadSkinAssets.mockReset()
})

describe('skin asset runtime decoration overlay', () => {
  it('loads a local Blob URL and removes it when the skin is disabled', async () => {
    const createObjectURL = vi.fn(() => 'blob:overlay')
    const revokeObjectURL = vi.fn()
    vi.stubGlobal('URL', { createObjectURL, revokeObjectURL })
    const styleElement = { dataset: {} as Record<string, string>, textContent: '', remove: vi.fn() }
    vi.stubGlobal('document', {
      createElement: vi.fn(() => styleElement),
      head: { appendChild: vi.fn() },
      fonts: { add: vi.fn(), delete: vi.fn() }
    })
    store.loadSkinAssets.mockResolvedValue(new Map([
      ['overlay', new Blob(['safe'], { type: 'image/png' })],
      [SKIN_LAYOUT_ASSET_ID, new Blob(['.ide-shell {}'], { type: 'text/css' })],
      [SKIN_VISUAL_ASSET_ID, new Blob(['.message {}'], { type: 'text/css' })]
    ]))
    const { root, properties } = rootElement()
    const skin = overlaySkin()

    await refreshSkinAssetRuntime(root, { enabled: true, skin })
    expect(properties.get('--skin-decoration-overlay-image')).toBe('url("blob:overlay")')
    expect(root.dataset.skinHasDecorationOverlay).toBe('true')

    await refreshSkinAssetRuntime(root, null)
    expect(properties.has('--skin-decoration-overlay-image')).toBe(false)
    expect(root.dataset.skinHasDecorationOverlay).toBeUndefined()
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:overlay')
  })

  it('injects verified layout and visual CSS together and removes them on disable', async () => {
    const styleElement = { dataset: {} as Record<string, string>, textContent: '', remove: vi.fn() }
    const appendChild = vi.fn()
    vi.stubGlobal('document', {
      createElement: vi.fn(() => styleElement),
      head: { appendChild },
      fonts: { add: vi.fn(), delete: vi.fn() }
    })
    vi.stubGlobal('URL', { createObjectURL: vi.fn(() => 'blob:asset'), revokeObjectURL: vi.fn() })
    store.loadSkinAssets.mockResolvedValue(new Map([
      [SKIN_LAYOUT_ASSET_ID, new Blob(['[data-skin-slot="app-shell"] { display: grid; }'], { type: 'text/css' })],
      [SKIN_VISUAL_ASSET_ID, new Blob(['[data-skin-slot="message-stream"] { color: lime; }'], { type: 'text/css' })]
    ]))
    const { root } = rootElement()
    const skin = overlaySkin()

    await refreshSkinAssetRuntime(root, { enabled: true, skin })
    expect(appendChild).toHaveBeenCalledWith(styleElement)
    expect(styleElement.dataset.workmodeOfficialSkin).toBe('overlay-test')
    expect(styleElement.textContent).toContain('app-shell')
    expect(styleElement.textContent).toContain('message-stream')

    await refreshSkinAssetRuntime(root, null)
    expect(styleElement.remove).toHaveBeenCalled()
  })
})
