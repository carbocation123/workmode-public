import { describe, expect, it } from 'vitest'
import {
  CUSTOM_SKIN_SCHEMA,
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

  it('repairs malformed persisted state to no custom skin', () => {
    expect(parseCustomSkinState('{broken')).toBeNull()
    expect(parseCustomSkinState(JSON.stringify({ version: 2, enabled: true, skin: {} }))).toBeNull()
    expect(parseCustomSkinState(JSON.stringify({ version: 1, enabled: true, skin: JSON.parse(valid) }))?.skin.id).toBe('ice-lab')
    expect(parseCustomSkinState(JSON.stringify({ version: 1, enabled: true, skin: JSON.parse(validHud) }))?.skin.chrome?.type).toBe('hud')
  })
})
