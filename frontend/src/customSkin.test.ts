import { describe, expect, it } from 'vitest'
import {
  CUSTOM_SKIN_SCHEMA,
  CUSTOM_SKIN_SCHEMA_V1,
  applyCustomSkinToRoot,
  buildCustomSkinVariables,
  isSupportedSkinFilename,
  parseCustomSkinState,
  parseDeclarativeSkin
} from './customSkin'

const valid = JSON.stringify({
  schema: CUSTOM_SKIN_SCHEMA,
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
  schema: CUSTOM_SKIN_SCHEMA,
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
  schema: CUSTOM_SKIN_SCHEMA,
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

describe('declarative custom skins', () => {
  it('accepts only JSON skin filenames before reading content', () => {
    expect(isSupportedSkinFilename('neon-ice.workmode-skin.json')).toBe(true)
    expect(isSupportedSkinFilename('neon-ice.JSON')).toBe(true)
    expect(isSupportedSkinFilename('neon-ice.css')).toBe(false)
    expect(isSupportedSkinFilename('neon-ice.json.exe')).toBe(false)
  })

  it('accepts and normalizes only the documented visual token schema', () => {
    const skin = parseDeclarativeSkin(valid)
    expect(skin.id).toBe('ice-lab')
    expect(skin.tokens.accent).toBe('#55ddff')
    expect(skin.tokens.lineWidth).toBe(2)
  })

  it('keeps workmode-skin/v1 files backward compatible', () => {
    const legacy = JSON.parse(valid)
    legacy.schema = CUSTOM_SKIN_SCHEMA_V1
    const skin = parseDeclarativeSkin(JSON.stringify(legacy))
    expect(skin.schema).toBe(CUSTOM_SKIN_SCHEMA_V1)
    expect(skin.tokens.accent).toBe('#55ddff')

    legacy.material = { preset: 'soft-cream' }
    expect(() => parseDeclarativeSkin(JSON.stringify(legacy))).toThrow('不支持的字段')
  })

  it('accepts bounded v2 material, geometry and decoration controls', () => {
    const skin = parseDeclarativeSkin(validCream)
    expect(skin.schema).toBe(CUSTOM_SKIN_SCHEMA)
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
    const skin = parseDeclarativeSkin(validHud)
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
    const variables = buildCustomSkinVariables(parseDeclarativeSkin(valid))
    expect(variables['--neon-line-width']).toBe('2px')
    expect(variables['--neon-panel-glass']).toBe('rgba(7, 18, 26, 0.12)')
    expect(JSON.stringify(variables)).not.toContain('url(')
    expect(Object.keys(variables).every((key) => key.startsWith('--'))).toBe(true)
  })

  it('compiles v2 material controls into finite generated CSS variables', () => {
    const variables = buildCustomSkinVariables(parseDeclarativeSkin(validCream))
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
    const skin = parseDeclarativeSkin(validHud)

    applyCustomSkinToRoot(root, { version: 1, enabled: true, skin })
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
    const skin = parseDeclarativeSkin(validCream)

    applyCustomSkinToRoot(root, { version: 1, enabled: true, skin })
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
    expect(parseCustomSkinState(JSON.stringify({ version: 1, enabled: true, skin: JSON.parse(validHud) }))?.skin.chrome?.type).toBe('hud')
  })
})
