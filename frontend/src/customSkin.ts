import type { ThemeId } from './theme'

export const CUSTOM_SKIN_STORAGE_KEY = 'workmode-public-custom-skin-v1'
export const CUSTOM_SKIN_SCHEMA_V1 = 'workmode-skin/v1'
export const CUSTOM_SKIN_SCHEMA = 'workmode-skin/v2'
export const CUSTOM_SKIN_MAX_BYTES = 32 * 1024

const THEME_IDS = new Set<ThemeId>(['lab', 'origin-ring', 'neon-space-lab', 'paper', 'observatory', 'high-contrast'])
const V1_TOP_LEVEL_KEYS = new Set(['schema', 'id', 'name', 'version', 'baseTheme', 'tokens', 'chrome'])
const V2_TOP_LEVEL_KEYS = new Set([
  'schema', 'id', 'name', 'version', 'baseTheme', 'tokens', 'chrome',
  'material', 'geometry', 'decoration'
])
const TOKEN_KEYS = new Set(['accent', 'background', 'surface', 'text', 'panelOpacity', 'lineWidth', 'radius', 'glow'])
const CHROME_KEYS = new Set([
  'type', 'title', 'subtitle', 'missionLabel', 'modelLabel', 'stateLabel', 'timeLabel',
  'panelGeometry', 'bubbleGeometry'
])
const PANEL_GEOMETRIES = new Set<DeclarativeHudChrome['panelGeometry']>(['stepped', 'continuous'])
const BUBBLE_GEOMETRIES = new Set<DeclarativeHudChrome['bubbleGeometry']>(['mirrored', 'continuous'])
const MATERIAL_KEYS = new Set(['preset', 'elevation', 'innerHighlight', 'grain', 'buttonDepth'])
const GEOMETRY_KEYS = new Set(['panelRadius', 'bubbleRadius', 'buttonRadius'])
const DECORATION_KEYS = new Set(['preset', 'density'])
const MATERIAL_PRESETS = new Set<DeclarativeSkinMaterial['preset']>(['soft-cream'])
const DECORATION_PRESETS = new Set<DeclarativeSkinDecoration['preset']>(['none', 'notebook'])
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

export interface DeclarativeSkinMaterial {
  preset: 'soft-cream'
  elevation?: number
  innerHighlight?: number
  grain?: number
  buttonDepth?: number
}

export interface DeclarativeSkinGeometry {
  panelRadius?: number
  bubbleRadius?: number
  buttonRadius?: number
}

export interface DeclarativeSkinDecoration {
  preset: 'none' | 'notebook'
  density?: number
}

export type DeclarativeSkinSchema = typeof CUSTOM_SKIN_SCHEMA_V1 | typeof CUSTOM_SKIN_SCHEMA

export interface DeclarativeSkin {
  schema: DeclarativeSkinSchema
  id: string
  name: string
  version: string
  baseTheme: ThemeId
  tokens: DeclarativeSkinTokens
  chrome?: DeclarativeHudChrome
  material?: DeclarativeSkinMaterial
  geometry?: DeclarativeSkinGeometry
  decoration?: DeclarativeSkinDecoration
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

function parseMaterial(value: unknown): DeclarativeSkinMaterial | undefined {
  if (value === undefined) return undefined
  if (!isObject(value)) throw new Error('material 必须是对象')
  assertKnownKeys(value, MATERIAL_KEYS, 'material')
  if (typeof value.preset !== 'string' || !MATERIAL_PRESETS.has(value.preset as DeclarativeSkinMaterial['preset'])) {
    throw new Error('material.preset 不是受支持的材质预设')
  }
  return {
    preset: value.preset as DeclarativeSkinMaterial['preset'],
    elevation: optionalNumber(value.elevation, 'material.elevation', 0, 1),
    innerHighlight: optionalNumber(value.innerHighlight, 'material.innerHighlight', 0, 1),
    grain: optionalNumber(value.grain, 'material.grain', 0, 1),
    buttonDepth: optionalNumber(value.buttonDepth, 'material.buttonDepth', 0, 8)
  }
}

function parseGeometry(value: unknown): DeclarativeSkinGeometry | undefined {
  if (value === undefined) return undefined
  if (!isObject(value)) throw new Error('geometry 必须是对象')
  assertKnownKeys(value, GEOMETRY_KEYS, 'geometry')
  const geometry: DeclarativeSkinGeometry = {
    panelRadius: optionalNumber(value.panelRadius, 'geometry.panelRadius', 0, 32),
    bubbleRadius: optionalNumber(value.bubbleRadius, 'geometry.bubbleRadius', 0, 32),
    buttonRadius: optionalNumber(value.buttonRadius, 'geometry.buttonRadius', 0, 24)
  }
  Object.keys(geometry).forEach((key) => {
    if (geometry[key as keyof DeclarativeSkinGeometry] === undefined) delete geometry[key as keyof DeclarativeSkinGeometry]
  })
  if (!Object.keys(geometry).length) throw new Error('geometry 至少需要一个几何参数')
  return geometry
}

function parseDecoration(value: unknown): DeclarativeSkinDecoration | undefined {
  if (value === undefined) return undefined
  if (!isObject(value)) throw new Error('decoration 必须是对象')
  assertKnownKeys(value, DECORATION_KEYS, 'decoration')
  if (typeof value.preset !== 'string' || !DECORATION_PRESETS.has(value.preset as DeclarativeSkinDecoration['preset'])) {
    throw new Error('decoration.preset 不是受支持的装饰预设')
  }
  return {
    preset: value.preset as DeclarativeSkinDecoration['preset'],
    density: optionalNumber(value.density, 'decoration.density', 0, 1)
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
  if (parsed.schema !== CUSTOM_SKIN_SCHEMA_V1 && parsed.schema !== CUSTOM_SKIN_SCHEMA) {
    throw new Error(`schema 必须是 ${CUSTOM_SKIN_SCHEMA_V1} 或 ${CUSTOM_SKIN_SCHEMA}`)
  }
  const schema = parsed.schema as DeclarativeSkinSchema
  assertKnownKeys(parsed, schema === CUSTOM_SKIN_SCHEMA_V1 ? V1_TOP_LEVEL_KEYS : V2_TOP_LEVEL_KEYS, '皮肤文件')

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
  const material = schema === CUSTOM_SKIN_SCHEMA ? parseMaterial(parsed.material) : undefined
  const geometry = schema === CUSTOM_SKIN_SCHEMA ? parseGeometry(parsed.geometry) : undefined
  const decoration = schema === CUSTOM_SKIN_SCHEMA ? parseDecoration(parsed.decoration) : undefined
  if (!Object.keys(tokens).length && !chrome && !material && !geometry && !decoration) {
    throw new Error('皮肤至少需要一个视觉 token、chrome、material、geometry 或 decoration')
  }

  return {
    schema,
    id,
    name,
    version,
    baseTheme: parsed.baseTheme as ThemeId,
    tokens,
    chrome,
    material,
    geometry,
    decoration
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
  if (skin.material) {
    const elevation = skin.material.elevation ?? 0.65
    const innerHighlight = skin.material.innerHighlight ?? 0.75
    const grain = skin.material.grain ?? 0.12
    variables['--custom-skin-shadow-y'] = `${Math.round(4 + elevation * 10)}px`
    variables['--custom-skin-shadow-blur'] = `${Math.round(12 + elevation * 28)}px`
    variables['--custom-skin-shadow-alpha'] = (0.04 + elevation * 0.12).toFixed(3)
    variables['--custom-skin-inner-highlight-alpha'] = (innerHighlight * 0.9).toFixed(3)
    variables['--custom-skin-grain-alpha'] = (grain * 0.3).toFixed(3)
    variables['--custom-skin-button-depth'] = `${skin.material.buttonDepth ?? 3}px`
  }
  if (skin.geometry?.panelRadius !== undefined) {
    variables['--custom-skin-panel-radius'] = `${skin.geometry.panelRadius}px`
  }
  if (skin.geometry?.bubbleRadius !== undefined) {
    variables['--custom-skin-bubble-radius'] = `${skin.geometry.bubbleRadius}px`
  }
  if (skin.geometry?.buttonRadius !== undefined) {
    variables['--custom-skin-button-radius'] = `${skin.geometry.buttonRadius}px`
  }
  if (skin.decoration) {
    variables['--custom-skin-decoration-density'] = String(skin.decoration.density ?? 0.3)
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
  '--custom-skin-line-width', '--custom-skin-radius', '--custom-skin-glow',
  '--custom-skin-shadow-y', '--custom-skin-shadow-blur', '--custom-skin-shadow-alpha',
  '--custom-skin-inner-highlight-alpha', '--custom-skin-grain-alpha', '--custom-skin-button-depth',
  '--custom-skin-panel-radius', '--custom-skin-bubble-radius', '--custom-skin-button-radius',
  '--custom-skin-decoration-density'
]

export function applyCustomSkinToRoot(root: HTMLElement, state: CustomSkinState | null) {
  CUSTOM_PROPERTIES.forEach((property) => root.style.removeProperty(property))
  delete root.dataset.customSkin
  delete root.dataset.customSkinChrome
  delete root.dataset.customSkinPanel
  delete root.dataset.customSkinBubble
  delete root.dataset.customSkinMaterial
  delete root.dataset.customSkinDecoration
  if (!state?.enabled) return
  root.dataset.customSkin = state.skin.id
  if (state.skin.chrome) {
    root.dataset.customSkinChrome = state.skin.chrome.type
    root.dataset.customSkinPanel = state.skin.chrome.panelGeometry || 'stepped'
    root.dataset.customSkinBubble = state.skin.chrome.bubbleGeometry || 'mirrored'
  }
  if (state.skin.material) root.dataset.customSkinMaterial = state.skin.material.preset
  if (state.skin.decoration) root.dataset.customSkinDecoration = state.skin.decoration.preset
  Object.entries(buildCustomSkinVariables(state.skin)).forEach(([property, value]) => root.style.setProperty(property, value))
}
