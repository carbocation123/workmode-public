import type { ThemeId } from './theme'

export const CUSTOM_SKIN_STORAGE_KEY = 'workmode-public-custom-skin-v1'
export const CUSTOM_SKIN_SCHEMA = 'workmode-skin/v1'
export const CUSTOM_SKIN_MAX_BYTES = 32 * 1024

const THEME_IDS = new Set<ThemeId>(['lab', 'origin-ring', 'neon-space-lab', 'paper', 'observatory', 'high-contrast'])
const TOP_LEVEL_KEYS = new Set(['schema', 'id', 'name', 'version', 'baseTheme', 'tokens', 'chrome'])
const TOKEN_KEYS = new Set(['accent', 'background', 'surface', 'text', 'panelOpacity', 'lineWidth', 'radius', 'glow'])
const CHROME_KEYS = new Set([
  'type', 'title', 'subtitle', 'missionLabel', 'modelLabel', 'stateLabel', 'timeLabel',
  'panelGeometry', 'bubbleGeometry'
])
const PANEL_GEOMETRIES = new Set<DeclarativeHudChrome['panelGeometry']>(['stepped', 'continuous'])
const BUBBLE_GEOMETRIES = new Set<DeclarativeHudChrome['bubbleGeometry']>(['mirrored', 'continuous'])
const COLOR_PATTERN = /^#[0-9a-fA-F]{6}$/
const ID_PATTERN = /^[a-z0-9][a-z0-9-]{0,39}$/
const VERSION_PATTERN = /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/

export function isSupportedSkinFilename(name: string) {
  return name.toLowerCase().endsWith('.json')
}

export interface DeclarativeSkinTokens {
  accent?: string
  background?: string
  surface?: string
  text?: string
  panelOpacity?: number
  lineWidth?: number
  radius?: number
  glow?: number
}

export interface DeclarativeHudChrome {
  type: 'hud'
  title?: string
  subtitle?: string
  missionLabel?: string
  modelLabel?: string
  stateLabel?: string
  timeLabel?: string
  panelGeometry?: 'stepped' | 'continuous'
  bubbleGeometry?: 'mirrored' | 'continuous'
}

export interface DeclarativeSkin {
  schema: typeof CUSTOM_SKIN_SCHEMA
  id: string
  name: string
  version: string
  baseTheme: ThemeId
  tokens: DeclarativeSkinTokens
  chrome?: DeclarativeHudChrome
}

export interface CustomSkinState {
  version: 1
  enabled: boolean
  skin: DeclarativeSkin
}

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function assertKnownKeys(value: Record<string, unknown>, allowed: Set<string>, label: string) {
  const unknown = Object.keys(value).filter((key) => !allowed.has(key))
  if (unknown.length) throw new Error(`${label}包含不支持的字段：${unknown.join(', ')}`)
}

function requiredString(value: unknown, label: string, maxLength: number) {
  if (typeof value !== 'string' || !value.trim() || value.length > maxLength) {
    throw new Error(`${label}必须是 1-${maxLength} 个字符的字符串`)
  }
  return value.trim()
}

function optionalColor(value: unknown, label: string) {
  if (value === undefined) return undefined
  if (typeof value !== 'string' || !COLOR_PATTERN.test(value)) throw new Error(`${label}必须是 #RRGGBB 颜色`)
  return value.toLowerCase()
}

function optionalNumber(value: unknown, label: string, min: number, max: number) {
  if (value === undefined) return undefined
  if (typeof value !== 'number' || !Number.isFinite(value) || value < min || value > max) {
    throw new Error(`${label}必须在 ${min}-${max} 之间`)
  }
  return value
}

function optionalLine(value: unknown, label: string, maxLength: number) {
  if (value === undefined) return undefined
  const line = requiredString(value, label, maxLength)
  if (/[\u0000-\u001f\u007f]/.test(line)) throw new Error(`${label}不能包含控制字符或换行`)
  return line
}

function parseHudChrome(value: unknown): DeclarativeHudChrome | undefined {
  if (value === undefined) return undefined
  if (!isObject(value)) throw new Error('chrome 必须是对象')
  assertKnownKeys(value, CHROME_KEYS, 'chrome')
  if (value.type !== 'hud') throw new Error('chrome.type 目前只支持 hud')
  if (value.panelGeometry !== undefined && !PANEL_GEOMETRIES.has(value.panelGeometry as DeclarativeHudChrome['panelGeometry'])) {
    throw new Error('chrome.panelGeometry 只支持 stepped 或 continuous')
  }
  if (value.bubbleGeometry !== undefined && !BUBBLE_GEOMETRIES.has(value.bubbleGeometry as DeclarativeHudChrome['bubbleGeometry'])) {
    throw new Error('chrome.bubbleGeometry 只支持 mirrored 或 continuous')
  }
  return {
    type: 'hud',
    title: optionalLine(value.title, 'chrome.title', 24),
    subtitle: optionalLine(value.subtitle, 'chrome.subtitle', 32),
    missionLabel: optionalLine(value.missionLabel, 'chrome.missionLabel', 24),
    modelLabel: optionalLine(value.modelLabel, 'chrome.modelLabel', 20),
    stateLabel: optionalLine(value.stateLabel, 'chrome.stateLabel', 20),
    timeLabel: optionalLine(value.timeLabel, 'chrome.timeLabel', 20),
    panelGeometry: value.panelGeometry as DeclarativeHudChrome['panelGeometry'],
    bubbleGeometry: value.bubbleGeometry as DeclarativeHudChrome['bubbleGeometry']
  }
}

export function parseDeclarativeSkin(raw: string): DeclarativeSkin {
  let parsed: unknown
  try {
    parsed = JSON.parse(raw)
  } catch {
    throw new Error('皮肤文件不是有效 JSON')
  }
  if (!isObject(parsed)) throw new Error('皮肤文件顶层必须是对象')
  assertKnownKeys(parsed, TOP_LEVEL_KEYS, '皮肤文件')
  if (parsed.schema !== CUSTOM_SKIN_SCHEMA) throw new Error(`schema 必须是 ${CUSTOM_SKIN_SCHEMA}`)

  const id = requiredString(parsed.id, 'id', 40)
  if (!ID_PATTERN.test(id)) throw new Error('id 只能包含小写字母、数字和连字符')
  const name = requiredString(parsed.name, 'name', 48)
  const version = requiredString(parsed.version, 'version', 32)
  if (!VERSION_PATTERN.test(version)) throw new Error('version 必须是 SemVer，例如 1.0.0')
  if (typeof parsed.baseTheme !== 'string' || !THEME_IDS.has(parsed.baseTheme as ThemeId)) {
    throw new Error('baseTheme 不是受支持的内置主题')
  }
  if (parsed.tokens !== undefined && !isObject(parsed.tokens)) throw new Error('tokens 必须是对象')
  const rawTokens = isObject(parsed.tokens) ? parsed.tokens : {}
  assertKnownKeys(rawTokens, TOKEN_KEYS, 'tokens')

  const tokens: DeclarativeSkinTokens = {
    accent: optionalColor(rawTokens.accent, 'accent'),
    background: optionalColor(rawTokens.background, 'background'),
    surface: optionalColor(rawTokens.surface, 'surface'),
    text: optionalColor(rawTokens.text, 'text'),
    panelOpacity: optionalNumber(rawTokens.panelOpacity, 'panelOpacity', 0, 0.8),
    lineWidth: optionalNumber(rawTokens.lineWidth, 'lineWidth', 1, 4),
    radius: optionalNumber(rawTokens.radius, 'radius', 0, 24),
    glow: optionalNumber(rawTokens.glow, 'glow', 0, 1)
  }
  Object.keys(tokens).forEach((key) => {
    if (tokens[key as keyof DeclarativeSkinTokens] === undefined) delete tokens[key as keyof DeclarativeSkinTokens]
  })
  const chrome = parseHudChrome(parsed.chrome)
  if (chrome && parsed.baseTheme !== 'neon-space-lab') {
    throw new Error('声明式 HUD 必须使用 baseTheme neon-space-lab')
  }
  if (!Object.keys(tokens).length && !chrome) throw new Error('皮肤至少需要一个视觉 token 或 chrome')

  return {
    schema: CUSTOM_SKIN_SCHEMA,
    id,
    name,
    version,
    baseTheme: parsed.baseTheme as ThemeId,
    tokens,
    chrome
  }
}

export function parseCustomSkinState(raw: string | null): CustomSkinState | null {
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

function hexRgb(color: string) {
  return {
    r: Number.parseInt(color.slice(1, 3), 16),
    g: Number.parseInt(color.slice(3, 5), 16),
    b: Number.parseInt(color.slice(5, 7), 16)
  }
}

function rgba(color: string, alpha: number) {
  const { r, g, b } = hexRgb(color)
  return `rgba(${r}, ${g}, ${b}, ${alpha})`
}

export function buildCustomSkinVariables(skin: DeclarativeSkin): Record<string, string> {
  const variables: Record<string, string> = {}
  const accent = skin.tokens.accent || '#43e8ff'
  const surface = skin.tokens.surface || '#07111a'
  const glow = skin.tokens.glow ?? 0.45

  if (skin.tokens.accent) {
    variables['--color-primary'] = accent
    variables['--color-primary-hover'] = accent
    variables['--color-primary-container'] = rgba(accent, 0.14)
    variables['--color-primary-border'] = rgba(accent, 0.48)
    variables['--color-primary-soft'] = rgba(accent, 0.08)
    variables['--color-primary-glow'] = rgba(accent, glow)
    variables['--neon-hologram-edge'] = rgba(accent, 0.88)
    variables['--neon-panel-edge'] = rgba(accent, 0.72)
  }
  if (skin.tokens.background) {
    variables['--color-surface-container-lowest'] = skin.tokens.background
    variables['--theme-app-background'] = skin.tokens.background
  }
  if (skin.tokens.surface) {
    variables['--color-surface-container-low'] = surface
    variables['--color-surface-container'] = surface
    variables['--color-surface-container-high'] = surface
  }
  if (skin.tokens.text) {
    variables['--color-on-surface'] = skin.tokens.text
    variables['--color-on-surface-variant'] = skin.tokens.text
  }
  if (skin.tokens.panelOpacity !== undefined) {
    variables['--neon-panel-glass'] = rgba(surface, skin.tokens.panelOpacity)
  }
  if (skin.tokens.lineWidth !== undefined) {
    variables['--neon-line-width'] = `${skin.tokens.lineWidth}px`
    variables['--custom-skin-line-width'] = `${skin.tokens.lineWidth}px`
  }
  if (skin.tokens.radius !== undefined) {
    variables['--neon-content-radius'] = `${skin.tokens.radius}px`
    variables['--custom-skin-radius'] = `${skin.tokens.radius}px`
  }
  variables['--custom-skin-glow'] = String(glow)
  return variables
}

const CUSTOM_PROPERTIES = [
  '--color-primary', '--color-primary-hover', '--color-primary-container', '--color-primary-border',
  '--color-primary-soft', '--color-primary-glow', '--color-surface-container-lowest',
  '--color-surface-container-low', '--color-surface-container', '--color-surface-container-high',
  '--color-on-surface', '--color-on-surface-variant', '--theme-app-background', '--neon-hologram-edge',
  '--neon-panel-edge', '--neon-panel-glass', '--neon-line-width', '--neon-content-radius',
  '--custom-skin-line-width', '--custom-skin-radius', '--custom-skin-glow'
]

export function applyCustomSkinToRoot(root: HTMLElement, state: CustomSkinState | null) {
  CUSTOM_PROPERTIES.forEach((property) => root.style.removeProperty(property))
  delete root.dataset.customSkin
  delete root.dataset.customSkinChrome
  delete root.dataset.customSkinPanel
  delete root.dataset.customSkinBubble
  if (!state?.enabled) return
  root.dataset.customSkin = state.skin.id
  if (state.skin.chrome) {
    root.dataset.customSkinChrome = state.skin.chrome.type
    root.dataset.customSkinPanel = state.skin.chrome.panelGeometry || 'stepped'
    root.dataset.customSkinBubble = state.skin.chrome.bubbleGeometry || 'mirrored'
  }
  Object.entries(buildCustomSkinVariables(state.skin)).forEach(([property, value]) => root.style.setProperty(property, value))
}
