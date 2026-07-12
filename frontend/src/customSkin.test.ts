import { describe, expect, it } from 'vitest'
import {
  CUSTOM_SKIN_SCHEMA,
  CUSTOM_SKIN_SCHEMA_V1,
  CUSTOM_SKIN_SCHEMA_V2,
  applyCustomSkinToRoot,
  buildCustomSkinVariables,
  getSkinFoundationTheme,
  getActiveCustomSkin,
  isLegacySkin,
  isSupportedSkinFilename,
  parseCustomSkinLibraryState,
  parseCustomSkinState,
  parseDeclarativeSkin,
  removeCustomSkinFromLibrary,
  upsertOfficialSkins
} from './customSkin'
import type { ParsedSkinImport } from './skinPackage'

function parseLegacy(raw: string) {
  const skin = parseDeclarativeSkin(raw)
  if (!isLegacySkin(skin)) throw new Error('Expected a legacy skin')
  return skin
}

function officialImport(skin: ReturnType<typeof parseDeclarativeSkin>, digest = 'a'.repeat(64)): ParsedSkinImport {
  return {
    skin: skin as ParsedSkinImport['skin'],
    assets: new Map(),
    styles: {
      layout: new Blob(['.ide-shell{}'], { type: 'text/css' }),
      visual: new Blob(['.message{}'], { type: 'text/css' })
    },
    trust: { keyId: 'official-test-key', packageDigest: digest }
  }
}

const valid = JSON.stringify({
  schema: CUSTOM_SKIN_SCHEMA_V2,
  id: 'ice-lab',
  name: 'Ice Lab',
  version: '1.0.0',
  baseTheme: 'neon-space-lab',
  tokens: {
    accent: '#55ddff',
    surface: '#07121a',
    panelOpacity: 0.12,
    lineWidth: 2,
    radius: 4,
    glow: 0.4
  }
})

const validHud = JSON.stringify({
  schema: CUSTOM_SKIN_SCHEMA_V2,
  id: 'ice-hud',
  name: 'Ice HUD',
  version: '1.0.0',
  baseTheme: 'neon-space-lab',
  chrome: {
    type: 'hud',
    title: 'ICE LAB',
    subtitle: 'LOCAL RESEARCH HUD',
    missionLabel: 'ACTIVE PROJECT',
    panelGeometry: 'continuous',
    bubbleGeometry: 'mirrored'
  }
})

const validCream = JSON.stringify({
  schema: CUSTOM_SKIN_SCHEMA_V2,
  id: 'cream-puff',
  name: '奶油泡芙实验室',
  version: '2.0.0',
  baseTheme: 'paper',
  tokens: {
    accent: '#df806f',
    background: '#f7e8cf',
    surface: '#fff9ed',
    text: '#5f5147',
    lineWidth: 2
  },
  material: {
    preset: 'soft-cream',
    elevation: 0.72,
    innerHighlight: 0.84,
    grain: 0.18,
    buttonDepth: 4
  },
  geometry: {
    panelRadius: 24,
    bubbleRadius: 18,
    buttonRadius: 14
  },
  decoration: {
    preset: 'notebook',
    density: 0.32
  }
})

const validV3 = JSON.stringify({
  schema: CUSTOM_SKIN_SCHEMA,
  id: 'amethyst-observatory',
  name: '紫晶星象塔',
  version: '3.0.0',
  foundation: 'dark',
  palette: {
    accent: '#a766e8',
    accentAlt: '#c5a460',
    background: '#090611',
    surface: '#160c23',
    surfaceRaised: '#251435',
    text: '#e5d9ef',
    textMuted: '#8d7ca7',
    border: '#6e5932',
    success: '#77c898',
    warning: '#c5a460',
    danger: '#9d4a71',
    selection: '#573076'
  },
  typography: { preset: 'scholar', scale: 1, assets: { display: 'display-font' } },
  material: { preset: 'obsidian', strength: 0.78, elevation: 0.42, grain: 0.12 },
  geometry: { lineWidth: 2, panelRadius: 4, bubbleRadius: 2, buttonRadius: 2 },
  components: {
    chrome: 'observatory',
    messages: 'manuscript',
    tools: 'ritual',
    context: 'dial',
    fileTree: 'archive'
  },
  icons: { preset: 'arcane', overrides: { folder: 'folder-icon' } },
  background: {
    asset: 'main-background',
    fit: 'cover',
    position: 'center',
    opacity: 0.42,
    overlay: '#090611',
    overlayOpacity: 0.58,
    blur: 0
  },
  effects: { preset: 'stars', intensity: 0.46, motion: 'subtle' },
  decoration: { preset: 'arcane', density: 0.4 },
  assets: [
    { id: 'main-background', path: 'backgrounds/main.webp', kind: 'image' },
    { id: 'folder-icon', path: 'icons/folder.png', kind: 'icon' },
    { id: 'display-font', path: 'fonts/display.woff2', kind: 'font' }
  ]
})

describe('declarative custom skins', () => {
  it('accepts a composable v3 skin without binding it to an achievement-gated base theme', () => {
    const skin = parseDeclarativeSkin(validV3)
    expect(skin.schema).toBe(CUSTOM_SKIN_SCHEMA)
    expect(skin).toEqual(expect.objectContaining({
      foundation: 'dark',
      components: expect.objectContaining({ chrome: 'observatory', tools: 'ritual' }),
      icons: expect.objectContaining({ preset: 'arcane' })
    }))
    expect(getSkinFoundationTheme(skin)).toBe('lab')
    expect('baseTheme' in skin).toBe(false)
  })

  it('accepts maintained console and gem-tech chrome presets as inert root state', () => {
    for (const chrome of ['console', 'gem-tech']) {
      const candidate = JSON.parse(validV3)
      candidate.components.chrome = chrome
      const skin = parseDeclarativeSkin(JSON.stringify(candidate))
      if (isLegacySkin(skin)) throw new Error('Expected a v3 skin')
      expect(skin.components.chrome).toBe(chrome)

      const root = {
        dataset: {} as Record<string, string>,
        style: { setProperty: () => undefined, removeProperty: () => undefined }
      } as unknown as HTMLElement
      applyCustomSkinToRoot(root, { enabled: true, skin })
      expect(root.dataset.skinChrome).toBe(chrome)
      applyCustomSkinToRoot(root, null)
      expect(root.dataset.skinChrome).toBeUndefined()
    }
  })

  it('accepts instrument, signal, gem and indexed component recipes as inert root state', () => {
    for (const context of ['signal', 'gem']) {
      const candidate = JSON.parse(validV3)
      candidate.components.tools = 'instrument'
      candidate.components.context = context
      candidate.components.fileTree = 'indexed'
      const skin = parseDeclarativeSkin(JSON.stringify(candidate))
      if (isLegacySkin(skin)) throw new Error('Expected a v3 skin')
      expect(skin.components).toEqual(expect.objectContaining({
        tools: 'instrument', context, fileTree: 'indexed'
      }))

      const root = {
        dataset: {} as Record<string, string>,
        style: { setProperty: () => undefined, removeProperty: () => undefined }
      } as unknown as HTMLElement
      applyCustomSkinToRoot(root, { enabled: true, skin })
      expect(root.dataset.skinTools).toBe('instrument')
      expect(root.dataset.skinContext).toBe(context)
      expect(root.dataset.skinFileTree).toBe('indexed')
    }
  })

  it('compiles v3 semantic palette, geometry and effects without accepting raw CSS', () => {
    const variables = buildCustomSkinVariables(parseDeclarativeSkin(validV3))
    expect(variables['--skin-color-accent']).toBe('#a766e8')
    expect(variables['--skin-color-text-muted']).toBe('#8d7ca7')
    expect(variables['--skin-panel-radius']).toBe('4px')
    expect(variables['--skin-background-opacity']).toBe('0.42')
    expect(JSON.stringify(variables)).not.toContain('url(')
    expect(JSON.stringify(variables)).not.toContain('javascript:')
  })

  it('accepts only maintained edge profiles and maps them to inert root state', () => {
    for (const edgeProfile of ['rounded', 'square', 'beveled', 'stepped']) {
      const profiled = JSON.parse(validV3)
      profiled.geometry.edgeProfile = edgeProfile
      const skin = parseDeclarativeSkin(JSON.stringify(profiled))
      if (isLegacySkin(skin)) throw new Error('Expected a v3 skin')
      expect(skin.geometry.edgeProfile).toBe(edgeProfile)

      const root = {
        dataset: {} as Record<string, string>,
        style: { setProperty: () => undefined, removeProperty: () => undefined }
      } as unknown as HTMLElement
      applyCustomSkinToRoot(root, { enabled: true, skin })
      expect(root.dataset.skinEdgeProfile).toBe(edgeProfile)
      applyCustomSkinToRoot(root, null)
      expect(root.dataset.skinEdgeProfile).toBeUndefined()
    }
  })

  it('rejects arbitrary edge geometry and raw clip-path declarations', () => {
    const arbitraryProfile = JSON.parse(validV3)
    arbitraryProfile.geometry.edgeProfile = 'polygon(0 0, 100% 0, 50% 100%)'
    expect(() => parseDeclarativeSkin(JSON.stringify(arbitraryProfile))).toThrow('geometry.edgeProfile')

    const rawClip = JSON.parse(validV3)
    rawClip.geometry.clipPath = 'polygon(0 0)'
    expect(() => parseDeclarativeSkin(JSON.stringify(rawClip))).toThrow('不支持的字段')
  })

  it('accepts one bounded local decoration overlay and requires an image asset', () => {
    const decorated = JSON.parse(validV3)
    decorated.decoration.overlay = {
      asset: 'main-background',
      fit: 'contain',
      position: 'right',
      opacity: 0.35
    }
    const skin = parseDeclarativeSkin(JSON.stringify(decorated))
    if (isLegacySkin(skin)) throw new Error('Expected a v3 skin')
    expect(skin.decoration.overlay).toEqual({
      asset: 'main-background',
      fit: 'contain',
      position: 'right',
      opacity: 0.35
    })

    const wrongKind = JSON.parse(validV3)
    wrongKind.decoration.overlay = { asset: 'folder-icon' }
    expect(() => parseDeclarativeSkin(JSON.stringify(wrongKind))).toThrow('不是 image 资源')
  })

  it('rejects unsafe decoration overlay controls and out-of-range opacity', () => {
    const dangling = JSON.parse(validV3)
    dangling.decoration.overlay = { asset: 'missing-overlay' }
    expect(() => parseDeclarativeSkin(JSON.stringify(dangling))).toThrow('missing-overlay')

    const opaque = JSON.parse(validV3)
    opaque.decoration.overlay = { asset: 'main-background', opacity: 0.9 }
    expect(() => parseDeclarativeSkin(JSON.stringify(opaque))).toThrow('0-0.65')

    const interactive = JSON.parse(validV3)
    interactive.decoration.overlay = { asset: 'main-background', pointerEvents: 'auto', zIndex: 9999 }
    expect(() => parseDeclarativeSkin(JSON.stringify(interactive))).toThrow('不支持的字段')

    const remote = JSON.parse(validV3)
    remote.decoration.overlay = { asset: 'https://example.com/overlay.png' }
    expect(() => parseDeclarativeSkin(JSON.stringify(remote))).toThrow()
  })

  it('accepts at most two unique effect layers while keeping legacy preset input compatible', () => {
    const layered = JSON.parse(validV3)
    delete layered.effects.preset
    layered.effects.layers = ['stars', 'glow']
    const skin = parseDeclarativeSkin(JSON.stringify(layered))
    if (isLegacySkin(skin)) throw new Error('Expected a v3 skin')

    expect(skin.effects).toEqual(expect.objectContaining({
      layers: ['stars', 'glow'],
      intensity: 0.46,
      motion: 'subtle'
    }))
    expect(skin.effects.preset).toBeUndefined()

    const legacyPreset = parseDeclarativeSkin(validV3)
    if (isLegacySkin(legacyPreset)) throw new Error('Expected a v3 skin')
    expect(legacyPreset.effects).toEqual(expect.objectContaining({ preset: 'stars' }))
    expect(legacyPreset.effects.layers).toBeUndefined()
  })

  it('round-trips a layered skin through the persistent library without dropping it', () => {
    const layered = JSON.parse(validV3)
    delete layered.effects.preset
    layered.effects.layers = ['stars', 'glow']
    const skin = parseDeclarativeSkin(JSON.stringify(layered))
    const stored = upsertOfficialSkins(parseCustomSkinLibraryState(null), [officialImport(skin)])
    const restored = parseCustomSkinLibraryState(JSON.stringify(stored))

    expect(restored.skins).toHaveLength(1)
    expect(restored.activeSkinId).toBe('amethyst-observatory')
    expect(isLegacySkin(restored.skins[0]) ? undefined : restored.skins[0].effects.layers).toEqual(['stars', 'glow'])
  })

  it('rejects conflicting, duplicate, empty, none and oversized effect layer declarations', () => {
    const cases: Array<[unknown, string]> = [
      { layers: ['stars', 'glow'], preset: 'stars' },
      { layers: ['stars', 'stars'] },
      { layers: [] },
      { layers: ['none'] },
      { layers: ['stars', 'glow', 'paper'] },
      { layers: ['stars', 'remote-css'] }
    ].map((effects) => [effects, 'effects'])

    for (const [effects, message] of cases) {
      const invalid = JSON.parse(validV3)
      invalid.effects = effects
      expect(() => parseDeclarativeSkin(JSON.stringify(invalid))).toThrow(message)
    }
  })

  it('rejects v3 remote resources, path traversal, unsupported assets and dangling references', () => {
    const remote = JSON.parse(validV3)
    remote.assets[0].path = 'https://example.com/background.webp'
    expect(() => parseDeclarativeSkin(JSON.stringify(remote))).toThrow()

    const traversal = JSON.parse(validV3)
    traversal.assets[0].path = '../background.webp'
    expect(() => parseDeclarativeSkin(JSON.stringify(traversal))).toThrow()

    const svg = JSON.parse(validV3)
    svg.assets[1].path = 'icons/folder.svg'
    expect(() => parseDeclarativeSkin(JSON.stringify(svg))).toThrow()

    const dangling = JSON.parse(validV3)
    dangling.background.asset = 'missing-background'
    expect(() => parseDeclarativeSkin(JSON.stringify(dangling))).toThrow('missing-background')

    const css = JSON.parse(validV3)
    css.css = '.ide-shell { display: none }'
    expect(() => parseDeclarativeSkin(JSON.stringify(css))).toThrow('不支持的字段')
  })

  it('maps v3 presets to inert root attributes and clears every v3 variable on disable', () => {
    const properties = new Map<string, string>()
    const root = {
      dataset: {} as Record<string, string>,
      style: {
        setProperty: (key: string, value: string) => properties.set(key, value),
        removeProperty: (key: string) => properties.delete(key)
      }
    } as unknown as HTMLElement
    const skin = parseDeclarativeSkin(validV3)

    applyCustomSkinToRoot(root, { enabled: true, skin })
    expect(root.dataset.customSkinSchema).toBe('v3')
    expect(root.dataset.skinMaterial).toBe('obsidian')
    expect(root.dataset.skinChrome).toBe('observatory')
    expect(root.dataset.skinIcons).toBe('arcane')
    expect(root.dataset.skinEffectStars).toBe('true')
    expect(properties.get('--skin-color-accent')).toBe('#a766e8')

    applyCustomSkinToRoot(root, null)
    expect(root.dataset.customSkinSchema).toBeUndefined()
    expect(root.dataset.skinMaterial).toBeUndefined()
    expect(root.dataset.skinEffectStars).toBeUndefined()
    expect(properties.has('--skin-color-accent')).toBe(false)
  })

  it('maps each effect layer to an independent root state and clears it on disable', () => {
    const layered = JSON.parse(validV3)
    delete layered.effects.preset
    layered.effects.layers = ['stars', 'glow']
    const skin = parseDeclarativeSkin(JSON.stringify(layered))
    const root = {
      dataset: {} as Record<string, string>,
      style: { setProperty: () => undefined, removeProperty: () => undefined }
    } as unknown as HTMLElement

    applyCustomSkinToRoot(root, { enabled: true, skin })
    expect(root.dataset.skinEffects).toBe('stars')
    expect(root.dataset.skinEffectStars).toBe('true')
    expect(root.dataset.skinEffectGlow).toBe('true')
    expect(root.dataset.skinEffectCrt).toBeUndefined()

    applyCustomSkinToRoot(root, null)
    expect(root.dataset.skinEffectStars).toBeUndefined()
    expect(root.dataset.skinEffectGlow).toBeUndefined()
  })

  it('accepts only official skin package filenames before reading content', () => {
    expect(isSupportedSkinFilename('neon-ice.workmode-skin.json')).toBe(false)
    expect(isSupportedSkinFilename('amethyst.workmode-skin')).toBe(true)
    expect(isSupportedSkinFilename('neon-ice.JSON')).toBe(false)
    expect(isSupportedSkinFilename('neon-ice.css')).toBe(false)
    expect(isSupportedSkinFilename('neon-ice.json.exe')).toBe(false)
  })

  it('accepts and normalizes only the documented visual token schema', () => {
    const skin = parseLegacy(valid)
    expect(skin.id).toBe('ice-lab')
    expect(skin.tokens.accent).toBe('#55ddff')
    expect(skin.tokens.lineWidth).toBe(2)
  })

  it('keeps workmode-skin/v1 files backward compatible', () => {
    const legacy = JSON.parse(valid)
    legacy.schema = CUSTOM_SKIN_SCHEMA_V1
    const skin = parseLegacy(JSON.stringify(legacy))
    expect(skin.schema).toBe(CUSTOM_SKIN_SCHEMA_V1)
    expect(skin.tokens.accent).toBe('#55ddff')

    legacy.material = { preset: 'soft-cream' }
    expect(() => parseDeclarativeSkin(JSON.stringify(legacy))).toThrow('不支持的字段')
  })

  it('accepts bounded v2 material, geometry and decoration controls', () => {
    const skin = parseLegacy(validCream)
    expect(skin.schema).toBe(CUSTOM_SKIN_SCHEMA_V2)
    expect(skin.material).toEqual(expect.objectContaining({ preset: 'soft-cream', elevation: 0.72 }))
    expect(skin.geometry).toEqual({ panelRadius: 24, bubbleRadius: 18, buttonRadius: 14 })
    expect(skin.decoration).toEqual({ preset: 'notebook', density: 0.32 })
  })

  it('rejects arbitrary material CSS, texture URLs, unknown presets and out-of-range values', () => {
    const arbitraryShadow = JSON.parse(validCream)
    arbitraryShadow.material.boxShadow = '0 0 999px red'
    expect(() => parseDeclarativeSkin(JSON.stringify(arbitraryShadow))).toThrow('不支持的字段')

    const textureUrl = JSON.parse(validCream)
    textureUrl.material.texture = 'url(https://example.com/grain.png)'
    expect(() => parseDeclarativeSkin(JSON.stringify(textureUrl))).toThrow('不支持的字段')

    const unknownPreset = JSON.parse(validCream)
    unknownPreset.material.preset = 'arbitrary-css'
    expect(() => parseDeclarativeSkin(JSON.stringify(unknownPreset))).toThrow('material.preset')

    const badDepth = JSON.parse(validCream)
    badDepth.material.buttonDepth = 80
    expect(() => parseDeclarativeSkin(JSON.stringify(badDepth))).toThrow('0-8')

    const badRadius = JSON.parse(validCream)
    badRadius.geometry.panelRadius = 200
    expect(() => parseDeclarativeSkin(JSON.stringify(badRadius))).toThrow('0-32')
  })

  it('accepts a pure declarative HUD with bounded labels and geometry presets', () => {
    const skin = parseLegacy(validHud)
    expect(skin.tokens).toEqual({})
    expect(skin.chrome).toEqual(expect.objectContaining({
      type: 'hud',
      title: 'ICE LAB',
      panelGeometry: 'continuous',
      bubbleGeometry: 'mirrored'
    }))
  })

  it('rejects arbitrary HUD markup, CSS fields and unsupported geometry', () => {
    const arbitraryCss = JSON.parse(validHud)
    arbitraryCss.chrome.css = '.send-btn { display: none }'
    expect(() => parseDeclarativeSkin(JSON.stringify(arbitraryCss))).toThrow('不支持的字段')

    const arbitraryMarkup = JSON.parse(validHud)
    arbitraryMarkup.chrome.html = '<button>fake</button>'
    expect(() => parseDeclarativeSkin(JSON.stringify(arbitraryMarkup))).toThrow('不支持的字段')

    const unknownGeometry = JSON.parse(validHud)
    unknownGeometry.chrome.panelGeometry = 'polygon(0 0)'
    expect(() => parseDeclarativeSkin(JSON.stringify(unknownGeometry))).toThrow('panelGeometry')
  })

  it('requires declarative HUD chrome to use the maintained Neon structural base', () => {
    const wrongBase = JSON.parse(validHud)
    wrongBase.baseTheme = 'paper'
    expect(() => parseDeclarativeSkin(JSON.stringify(wrongBase))).toThrow('neon-space-lab')
  })

  it('rejects arbitrary CSS, scripts, assets, URLs and unknown keys', () => {
    for (const extra of [
      { css: 'body { display: none }' },
      { javascript: 'alert(1)' },
      { assets: ['https://example.com/a.png'] },
      { permissions: ['project.read'] }
    ]) {
      const parsed = JSON.parse(valid)
      Object.assign(parsed, extra)
      expect(() => parseDeclarativeSkin(JSON.stringify(parsed))).toThrow('不支持的字段')
    }
  })

  it('rejects malformed colors and out-of-range material controls', () => {
    const badColor = JSON.parse(valid)
    badColor.tokens.accent = 'url(https://example.com/x)'
    expect(() => parseDeclarativeSkin(JSON.stringify(badColor))).toThrow('#RRGGBB')

    const badWidth = JSON.parse(valid)
    badWidth.tokens.lineWidth = 20
    expect(() => parseDeclarativeSkin(JSON.stringify(badWidth))).toThrow('1-4')
  })

  it('builds a finite allowlist of CSS variables without raw CSS or URLs', () => {
    const variables = buildCustomSkinVariables(parseLegacy(valid))
    expect(variables['--neon-line-width']).toBe('2px')
    expect(variables['--neon-panel-glass']).toBe('rgba(7, 18, 26, 0.12)')
    expect(JSON.stringify(variables)).not.toContain('url(')
    expect(Object.keys(variables).every((key) => key.startsWith('--'))).toBe(true)
  })

  it('compiles v2 material controls into finite generated CSS variables', () => {
    const variables = buildCustomSkinVariables(parseLegacy(validCream))
    expect(variables['--custom-skin-panel-radius']).toBe('24px')
    expect(variables['--custom-skin-bubble-radius']).toBe('18px')
    expect(variables['--custom-skin-button-radius']).toBe('14px')
    expect(variables['--custom-skin-button-depth']).toBe('4px')
    expect(Number(variables['--custom-skin-shadow-alpha'])).toBeGreaterThan(0)
    expect(JSON.stringify(variables)).not.toContain('url(')
    expect(JSON.stringify(variables)).not.toContain('box-shadow')
  })

  it('maps structural choices to inert root data attributes and clears them on disable', () => {
    const properties = new Map<string, string>()
    const root = {
      dataset: {} as Record<string, string>,
      style: {
        setProperty: (key: string, value: string) => properties.set(key, value),
        removeProperty: (key: string) => properties.delete(key)
      }
    } as unknown as HTMLElement
    const skin = parseLegacy(validHud)

    applyCustomSkinToRoot(root, { enabled: true, skin })
    expect(root.dataset.customSkinChrome).toBe('hud')
    expect(root.dataset.customSkinPanel).toBe('continuous')
    expect(root.dataset.customSkinBubble).toBe('mirrored')

    applyCustomSkinToRoot(root, null)
    expect(root.dataset.customSkinChrome).toBeUndefined()
    expect(root.dataset.customSkinPanel).toBeUndefined()
    expect(root.dataset.customSkinBubble).toBeUndefined()
  })

  it('maps v2 presets to inert data attributes and clears them on disable', () => {
    const root = {
      dataset: {} as Record<string, string>,
      style: { setProperty: () => undefined, removeProperty: () => undefined }
    } as unknown as HTMLElement
    const skin = parseLegacy(validCream)

    applyCustomSkinToRoot(root, { enabled: true, skin })
    expect(root.dataset.customSkinMaterial).toBe('soft-cream')
    expect(root.dataset.customSkinDecoration).toBe('notebook')

    applyCustomSkinToRoot(root, null)
    expect(root.dataset.customSkinMaterial).toBeUndefined()
    expect(root.dataset.customSkinDecoration).toBeUndefined()
  })

  it('repairs malformed persisted state to no custom skin', () => {
    expect(parseCustomSkinState('{broken')).toBeNull()
    expect(parseCustomSkinState(JSON.stringify({ version: 2, enabled: true, skin: {} }))).toBeNull()
    expect(parseCustomSkinState(JSON.stringify({ version: 1, enabled: true, skin: JSON.parse(valid) }))?.skin.id).toBe('ice-lab')
    const restoredHud = parseCustomSkinState(JSON.stringify({ version: 1, enabled: true, skin: JSON.parse(validHud) }))
    expect(restoredHud && isLegacySkin(restoredHud.skin) ? restoredHud.skin.chrome?.type : undefined).toBe('hud')
  })

  it('clears legacy unsigned skin state instead of grandfathering it into the official library', () => {
    const library = parseCustomSkinLibraryState(JSON.stringify({
      version: 1,
      enabled: true,
      skin: JSON.parse(valid)
    }))

    expect(library.version).toBe(4)
    expect(library.activeSkinId).toBeNull()
    expect(library.skins).toEqual([])
    expect(getActiveCustomSkin(library)).toBeNull()
  })

  it('stores multiple skins, replaces matching ids and remembers the active selection', () => {
    const ice = parseLegacy(valid)
    const cream = parseLegacy(validCream)
    const updatedIce = { ...ice, name: 'Ice Lab Updated', version: '1.1.0' }

    let library = parseCustomSkinLibraryState(null)
    library = upsertOfficialSkins(library, [officialImport(ice), officialImport(cream, 'b'.repeat(64))])
    expect(library.skins.map((skin) => skin.id)).toEqual(['ice-lab', 'cream-puff'])
    expect(library.activeSkinId).toBe('cream-puff')

    library = upsertOfficialSkins(library, [officialImport(updatedIce, 'c'.repeat(64))])
    expect(library.skins).toHaveLength(2)
    expect(library.skins.find((skin) => skin.id === 'ice-lab')?.name).toBe('Ice Lab Updated')
    expect(library.activeSkinId).toBe('ice-lab')

    const restored = parseCustomSkinLibraryState(JSON.stringify(library))
    expect(restored.skins).toHaveLength(2)
    expect(restored.activeSkinId).toBe('ice-lab')
  })

  it('removes only the selected library skin and safely clears a missing active id', () => {
    const ice = parseLegacy(valid)
    const cream = parseLegacy(validCream)
    const library = upsertOfficialSkins(parseCustomSkinLibraryState(null), [officialImport(ice), officialImport(cream, 'b'.repeat(64))])
    const removed = removeCustomSkinFromLibrary(library, 'cream-puff')

    expect(removed.skins.map((skin) => skin.id)).toEqual(['ice-lab'])
    expect(removed.activeSkinId).toBeNull()
    expect(getActiveCustomSkin(removed)).toBeNull()

    const malformedActive = parseCustomSkinLibraryState(JSON.stringify({
      version: 4,
      activeSkinId: 'not-installed',
      skins: [JSON.parse(valid)],
      receipts: { 'ice-lab': { keyId: 'official-test-key', packageDigest: 'a'.repeat(64) } }
    }))
    expect(malformedActive.activeSkinId).toBeNull()
  })
})
