import type { ThemeId } from './theme'

export const CUSTOM_SKIN_SCHEMA_V1 = 'workmode-skin/v1'
export const CUSTOM_SKIN_SCHEMA_V2 = 'workmode-skin/v2'
export const CUSTOM_SKIN_SCHEMA = 'workmode-skin/v3'
export const CUSTOM_SKIN_MANIFEST_MAX_BYTES = 256 * 1024

const THEME_IDS = new Set<ThemeId>(['lab', 'origin-ring', 'neon-space-lab', 'paper', 'observatory', 'high-contrast'])
const V1_TOP_LEVEL_KEYS = new Set(['schema', 'id', 'name', 'version', 'baseTheme', 'tokens', 'chrome'])
const V2_TOP_LEVEL_KEYS = new Set([
  'schema', 'id', 'name', 'version', 'baseTheme', 'tokens', 'chrome',
  'material', 'geometry', 'decoration'
])
const V3_TOP_LEVEL_KEYS = new Set([
  'schema', 'id', 'name', 'version', 'foundation', 'palette', 'typography', 'material',
  'geometry', 'components', 'icons', 'background', 'effects', 'decoration', 'assets'
])
const TOKEN_KEYS = new Set(['accent', 'background', 'surface', 'text', 'panelOpacity', 'lineWidth', 'radius', 'glow'])
const CHROME_KEYS = new Set([
  'type', 'title', 'subtitle', 'missionLabel', 'modelLabel', 'stateLabel', 'timeLabel',
  'panelGeometry', 'bubbleGeometry'
])
const LEGACY_MATERIAL_KEYS = new Set(['preset', 'elevation', 'innerHighlight', 'grain', 'buttonDepth'])
const LEGACY_GEOMETRY_KEYS = new Set(['panelRadius', 'bubbleRadius', 'buttonRadius'])
const LEGACY_DECORATION_KEYS = new Set(['preset', 'density'])
const PALETTE_KEYS = new Set([
  'accent', 'accentAlt', 'background', 'surface', 'surfaceRaised', 'text', 'textMuted',
  'border', 'success', 'warning', 'danger', 'selection'
])
const TYPOGRAPHY_KEYS = new Set(['preset', 'scale', 'assets'])
const TYPOGRAPHY_ASSET_KEYS = new Set(['ui', 'content', 'code', 'display'])
const MATERIAL_KEYS = new Set(['preset', 'strength', 'elevation', 'innerHighlight', 'grain', 'buttonDepth'])
const GEOMETRY_KEYS = new Set(['lineWidth', 'panelRadius', 'bubbleRadius', 'buttonRadius', 'edgeProfile'])
const COMPONENT_KEYS = new Set(['chrome', 'messages', 'tools', 'context', 'fileTree'])
const ICON_KEYS = new Set(['preset', 'overrides'])
const BACKGROUND_KEYS = new Set(['asset', 'fit', 'position', 'opacity', 'overlay', 'overlayOpacity', 'blur'])
const EFFECT_KEYS = new Set(['preset', 'layers', 'intensity', 'motion'])
const DECORATION_KEYS = new Set(['preset', 'density', 'overlay'])
const DECORATION_OVERLAY_KEYS = new Set(['asset', 'fit', 'position', 'opacity'])
const ASSET_KEYS = new Set(['id', 'path', 'kind'])

const PANEL_GEOMETRIES = new Set<NonNullable<DeclarativeHudChrome['panelGeometry']>>(['stepped', 'continuous'])
const BUBBLE_GEOMETRIES = new Set<NonNullable<DeclarativeHudChrome['bubbleGeometry']>>(['mirrored', 'continuous'])
const LEGACY_MATERIAL_PRESETS = new Set<LegacySkinMaterial['preset']>(['soft-cream'])
const LEGACY_DECORATION_PRESETS = new Set<LegacySkinDecoration['preset']>(['none', 'notebook'])
const FOUNDATIONS = new Set<V3SkinFoundation>(['dark', 'light'])
const TYPOGRAPHY_PRESETS = new Set<V3TypographyPreset>(['system', 'scholar', 'terminal', 'pixel', 'editorial'])
const MATERIAL_PRESETS = new Set<V3MaterialPreset>(['flat', 'glass', 'soft-cream', 'paper', 'metal', 'crt', 'obsidian'])
const EDGE_PROFILES = new Set<V3EdgeProfile>(['rounded', 'square', 'beveled', 'stepped'])
const CHROME_PRESETS = new Set<V3ChromePreset>(['none', 'hud', 'terminal', 'observatory', 'console', 'gem-tech'])
const MESSAGE_PRESETS = new Set<V3MessagePreset>(['bubbles', 'log', 'manuscript', 'pixel'])
const TOOL_PRESETS = new Set<V3ToolPreset>(['card', 'compact', 'terminal', 'ritual', 'instrument'])
const CONTEXT_PRESETS = new Set<V3ContextPreset>(['bar', 'ring', 'dial', 'signal', 'gem'])
const FILE_TREE_PRESETS = new Set<V3FileTreePreset>(['standard', 'compact', 'terminal', 'archive', 'indexed'])
const ICON_PRESETS = new Set<V3IconPreset>(['default', 'pixel', 'terminal', 'archive', 'gem', 'arcane'])
const EFFECT_PRESETS = new Set<V3EffectPreset>(['none', 'glow', 'crt', 'stars', 'paper'])
const ACTIVE_EFFECT_PRESETS = new Set<V3ActiveEffectPreset>(['glow', 'crt', 'stars', 'paper'])
const MOTION_PRESETS = new Set<V3MotionPreset>(['none', 'subtle', 'full'])
const DECORATION_PRESETS = new Set<V3DecorationPreset>(['none', 'notebook', 'hud', 'ink', 'arcane', 'retro'])
const BACKGROUND_FITS = new Set<V3BackgroundFit>(['cover', 'contain', 'tile'])
const BACKGROUND_POSITIONS = new Set<V3BackgroundPosition>(['center', 'top', 'bottom', 'left', 'right'])
const ASSET_KINDS = new Set<SkinAssetKind>(['image', 'icon', 'font'])
const ICON_SLOTS = new Set<SkinIconSlot>([
  'project', 'settings', 'folder', 'folder-open', 'markdown', 'pdf', 'image', 'code',
  'data', 'archive', 'text', 'media', 'file', 'session', 'tool-running', 'tool-done', 'tool-error'
])
const COLOR_PATTERN = /^#[0-9a-fA-F]{6}$/
const ID_PATTERN = /^[a-z0-9][a-z0-9-]{0,39}$/
const ASSET_ID_PATTERN = /^[a-z0-9][a-z0-9-]{0,47}$/
const VERSION_PATTERN = /^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/

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

export interface LegacySkinMaterial {
  preset: 'soft-cream'
  elevation?: number
  innerHighlight?: number
  grain?: number
  buttonDepth?: number
}

export interface LegacySkinGeometry {
  panelRadius?: number
  bubbleRadius?: number
  buttonRadius?: number
}

export interface LegacySkinDecoration {
  preset: 'none' | 'notebook'
  density?: number
}

export interface LegacyDeclarativeSkin {
  schema: typeof CUSTOM_SKIN_SCHEMA_V1 | typeof CUSTOM_SKIN_SCHEMA_V2
  id: string
  name: string
  version: string
  baseTheme: ThemeId
  tokens: DeclarativeSkinTokens
  chrome?: DeclarativeHudChrome
  material?: LegacySkinMaterial
  geometry?: LegacySkinGeometry
  decoration?: LegacySkinDecoration
}

export type V3SkinFoundation = 'dark' | 'light'
export type V3TypographyPreset = 'system' | 'scholar' | 'terminal' | 'pixel' | 'editorial'
export type V3MaterialPreset = 'flat' | 'glass' | 'soft-cream' | 'paper' | 'metal' | 'crt' | 'obsidian'
export type V3EdgeProfile = 'rounded' | 'square' | 'beveled' | 'stepped'
export type V3ChromePreset = 'none' | 'hud' | 'terminal' | 'observatory' | 'console' | 'gem-tech'
export type V3MessagePreset = 'bubbles' | 'log' | 'manuscript' | 'pixel'
export type V3ToolPreset = 'card' | 'compact' | 'terminal' | 'ritual' | 'instrument'
export type V3ContextPreset = 'bar' | 'ring' | 'dial' | 'signal' | 'gem'
export type V3FileTreePreset = 'standard' | 'compact' | 'terminal' | 'archive' | 'indexed'
export type V3IconPreset = 'default' | 'pixel' | 'terminal' | 'archive' | 'gem' | 'arcane'
export type V3EffectPreset = 'none' | 'glow' | 'crt' | 'stars' | 'paper'
export type V3ActiveEffectPreset = Exclude<V3EffectPreset, 'none'>
export type V3MotionPreset = 'none' | 'subtle' | 'full'
export type V3DecorationPreset = 'none' | 'notebook' | 'hud' | 'ink' | 'arcane' | 'retro'
export type V3BackgroundFit = 'cover' | 'contain' | 'tile'
export type V3BackgroundPosition = 'center' | 'top' | 'bottom' | 'left' | 'right'
export type SkinAssetKind = 'image' | 'icon' | 'font'
export type SkinFontRole = 'ui' | 'content' | 'code' | 'display'
export type SkinIconSlot =
  | 'project' | 'settings' | 'folder' | 'folder-open' | 'markdown' | 'pdf' | 'image'
  | 'code' | 'data' | 'archive' | 'text' | 'media' | 'file' | 'session'
  | 'tool-running' | 'tool-done' | 'tool-error'

export interface V3SkinPalette {
  accent?: string
  accentAlt?: string
  background?: string
  surface?: string
  surfaceRaised?: string
  text?: string
  textMuted?: string
  border?: string
  success?: string
  warning?: string
  danger?: string
  selection?: string
}

export interface V3SkinTypography {
  preset: V3TypographyPreset
  scale?: number
  assets?: Partial<Record<SkinFontRole, string>>
}

export interface V3SkinMaterial {
  preset: V3MaterialPreset
  strength?: number
  elevation?: number
  innerHighlight?: number
  grain?: number
  buttonDepth?: number
}

export interface V3SkinGeometry {
  lineWidth?: number
  panelRadius?: number
  bubbleRadius?: number
  buttonRadius?: number
  edgeProfile?: V3EdgeProfile
}

export interface V3SkinComponents {
  chrome: V3ChromePreset
  messages: V3MessagePreset
  tools: V3ToolPreset
  context: V3ContextPreset
  fileTree: V3FileTreePreset
}

export interface V3SkinIcons {
  preset: V3IconPreset
  overrides?: Partial<Record<SkinIconSlot, string>>
}

export interface V3SkinBackground {
  asset: string
  fit?: V3BackgroundFit
  position?: V3BackgroundPosition
  opacity?: number
  overlay?: string
  overlayOpacity?: number
  blur?: number
}

export interface V3SkinEffects {
  preset?: V3EffectPreset
  layers?: V3ActiveEffectPreset[]
  intensity?: number
  motion?: V3MotionPreset
}

export interface V3SkinDecoration {
  preset: V3DecorationPreset
  density?: number
  overlay?: V3SkinDecorationOverlay
}

export interface V3SkinDecorationOverlay {
  asset: string
  fit?: V3BackgroundFit
  position?: V3BackgroundPosition
  opacity?: number
}

export interface SkinAssetDescriptor {
  id: string
  path: string
  kind: SkinAssetKind
}

export interface V3DeclarativeSkin {
  schema: typeof CUSTOM_SKIN_SCHEMA
  id: string
  name: string
  version: string
  foundation: V3SkinFoundation
  palette: V3SkinPalette
  typography: V3SkinTypography
  material: V3SkinMaterial
  geometry: V3SkinGeometry
  components: V3SkinComponents
  icons: V3SkinIcons
  background?: V3SkinBackground
  effects: V3SkinEffects
  decoration: V3SkinDecoration
  assets: SkinAssetDescriptor[]
}

export type DeclarativeSkin = LegacyDeclarativeSkin | V3DeclarativeSkin
export type DeclarativeSkinSchema = DeclarativeSkin['schema']

export interface ActiveCustomSkin {
  enabled: true
  skin: DeclarativeSkin
}

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function assertKnownKeys(value: Record<string, unknown>, allowed: Set<string>, label: string) {
  const unknown = Object.keys(value).filter((key) => !allowed.has(key))
  if (unknown.length) throw new Error(`${label}包含不支持的字段：${unknown.join(', ')}`)
}

function objectValue(value: unknown, label: string) {
  if (!isObject(value)) throw new Error(`${label}必须是对象`)
  return value
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

function enumValue<T extends string>(value: unknown, allowed: Set<T>, label: string, fallback?: T): T {
  if (value === undefined && fallback !== undefined) return fallback
  if (typeof value !== 'string' || !allowed.has(value as T)) throw new Error(`${label}不是受支持的值`)
  return value as T
}

function compact<T extends object>(value: T): T {
  Object.keys(value).forEach((key) => {
    if (value[key as keyof T] === undefined) delete value[key as keyof T]
  })
  return value
}

function parseEffectLayers(value: unknown): V3ActiveEffectPreset[] | undefined {
  if (value === undefined) return undefined
  if (!Array.isArray(value)) throw new Error('effects.layers 必须是数组')
  if (value.length < 1 || value.length > 2) throw new Error('effects.layers 必须包含 1-2 个效果')
  const layers = value.map((item, index) => enumValue(item, ACTIVE_EFFECT_PRESETS, `effects.layers[${index}]`))
  if (new Set(layers).size !== layers.length) throw new Error('effects.layers 不允许重复效果')
  return layers
}

function parseIdentity(parsed: Record<string, unknown>) {
  const id = requiredString(parsed.id, 'id', 40)
  if (!ID_PATTERN.test(id)) throw new Error('id 只能包含小写字母、数字和连字符')
  const name = requiredString(parsed.name, 'name', 48)
  const version = requiredString(parsed.version, 'version', 32)
  if (!VERSION_PATTERN.test(version)) throw new Error('version 必须是 SemVer，例如 1.0.0')
  return { id, name, version }
}

function parseHudChrome(value: unknown): DeclarativeHudChrome | undefined {
  if (value === undefined) return undefined
  const chrome = objectValue(value, 'chrome')
  assertKnownKeys(chrome, CHROME_KEYS, 'chrome')
  if (chrome.type !== 'hud') throw new Error('chrome.type 目前只支持 hud')
  return compact({
    type: 'hud' as const,
    title: optionalLine(chrome.title, 'chrome.title', 24),
    subtitle: optionalLine(chrome.subtitle, 'chrome.subtitle', 32),
    missionLabel: optionalLine(chrome.missionLabel, 'chrome.missionLabel', 24),
    modelLabel: optionalLine(chrome.modelLabel, 'chrome.modelLabel', 20),
    stateLabel: optionalLine(chrome.stateLabel, 'chrome.stateLabel', 20),
    timeLabel: optionalLine(chrome.timeLabel, 'chrome.timeLabel', 20),
    panelGeometry: chrome.panelGeometry === undefined
      ? undefined
      : enumValue(chrome.panelGeometry, PANEL_GEOMETRIES, 'chrome.panelGeometry'),
    bubbleGeometry: chrome.bubbleGeometry === undefined
      ? undefined
      : enumValue(chrome.bubbleGeometry, BUBBLE_GEOMETRIES, 'chrome.bubbleGeometry')
  })
}

function parseLegacyMaterial(value: unknown): LegacySkinMaterial | undefined {
  if (value === undefined) return undefined
  const material = objectValue(value, 'material')
  assertKnownKeys(material, LEGACY_MATERIAL_KEYS, 'material')
  return compact({
    preset: enumValue(material.preset, LEGACY_MATERIAL_PRESETS, 'material.preset'),
    elevation: optionalNumber(material.elevation, 'material.elevation', 0, 1),
    innerHighlight: optionalNumber(material.innerHighlight, 'material.innerHighlight', 0, 1),
    grain: optionalNumber(material.grain, 'material.grain', 0, 1),
    buttonDepth: optionalNumber(material.buttonDepth, 'material.buttonDepth', 0, 8)
  })
}

function parseLegacyGeometry(value: unknown): LegacySkinGeometry | undefined {
  if (value === undefined) return undefined
  const geometry = objectValue(value, 'geometry')
  assertKnownKeys(geometry, LEGACY_GEOMETRY_KEYS, 'geometry')
  const parsed = compact({
    panelRadius: optionalNumber(geometry.panelRadius, 'geometry.panelRadius', 0, 32),
    bubbleRadius: optionalNumber(geometry.bubbleRadius, 'geometry.bubbleRadius', 0, 32),
    buttonRadius: optionalNumber(geometry.buttonRadius, 'geometry.buttonRadius', 0, 24)
  })
  if (!Object.keys(parsed).length) throw new Error('geometry 至少需要一个几何参数')
  return parsed
}

function parseLegacyDecoration(value: unknown): LegacySkinDecoration | undefined {
  if (value === undefined) return undefined
  const decoration = objectValue(value, 'decoration')
  assertKnownKeys(decoration, LEGACY_DECORATION_KEYS, 'decoration')
  return compact({
    preset: enumValue(decoration.preset, LEGACY_DECORATION_PRESETS, 'decoration.preset'),
    density: optionalNumber(decoration.density, 'decoration.density', 0, 1)
  })
}

function parseLegacySkin(parsed: Record<string, unknown>, schema: LegacyDeclarativeSkin['schema']): LegacyDeclarativeSkin {
  assertKnownKeys(parsed, schema === CUSTOM_SKIN_SCHEMA_V1 ? V1_TOP_LEVEL_KEYS : V2_TOP_LEVEL_KEYS, '皮肤文件')
  const identity = parseIdentity(parsed)
  if (typeof parsed.baseTheme !== 'string' || !THEME_IDS.has(parsed.baseTheme as ThemeId)) {
    throw new Error('baseTheme 不是受支持的内置主题')
  }
  const rawTokens = parsed.tokens === undefined ? {} : objectValue(parsed.tokens, 'tokens')
  assertKnownKeys(rawTokens, TOKEN_KEYS, 'tokens')
  const tokens = compact({
    accent: optionalColor(rawTokens.accent, 'accent'),
    background: optionalColor(rawTokens.background, 'background'),
    surface: optionalColor(rawTokens.surface, 'surface'),
    text: optionalColor(rawTokens.text, 'text'),
    panelOpacity: optionalNumber(rawTokens.panelOpacity, 'panelOpacity', 0, 0.8),
    lineWidth: optionalNumber(rawTokens.lineWidth, 'lineWidth', 1, 4),
    radius: optionalNumber(rawTokens.radius, 'radius', 0, 24),
    glow: optionalNumber(rawTokens.glow, 'glow', 0, 1)
  })
  const chrome = parseHudChrome(parsed.chrome)
  if (chrome && parsed.baseTheme !== 'neon-space-lab') throw new Error('声明式 HUD 必须使用 baseTheme neon-space-lab')
  const material = schema === CUSTOM_SKIN_SCHEMA_V2 ? parseLegacyMaterial(parsed.material) : undefined
  const geometry = schema === CUSTOM_SKIN_SCHEMA_V2 ? parseLegacyGeometry(parsed.geometry) : undefined
  const decoration = schema === CUSTOM_SKIN_SCHEMA_V2 ? parseLegacyDecoration(parsed.decoration) : undefined
  if (!Object.keys(tokens).length && !chrome && !material && !geometry && !decoration) {
    throw new Error('皮肤至少需要一个视觉 token、chrome、material、geometry 或 decoration')
  }
  return compact({ schema, ...identity, baseTheme: parsed.baseTheme as ThemeId, tokens, chrome, material, geometry, decoration })
}

export function isSafeSkinAssetPath(path: string) {
  if (!path || path.length > 160 || path.startsWith('/') || path.includes('\\') || path.includes(':') || path.includes('\0')) return false
  const segments = path.split('/')
  return segments.every((segment) => Boolean(segment) && segment !== '.' && segment !== '..' && /^[0-9A-Za-z._-]+$/.test(segment))
}

export function skinAssetMime(descriptor: SkinAssetDescriptor) {
  const path = descriptor.path.toLowerCase()
  if (descriptor.kind === 'font' && path.endsWith('.woff2')) return 'font/woff2'
  if ((descriptor.kind === 'image' || descriptor.kind === 'icon') && path.endsWith('.png')) return 'image/png'
  if ((descriptor.kind === 'image' || descriptor.kind === 'icon') && (path.endsWith('.jpg') || path.endsWith('.jpeg'))) return 'image/jpeg'
  if ((descriptor.kind === 'image' || descriptor.kind === 'icon') && path.endsWith('.webp')) return 'image/webp'
  return null
}

function parseAssets(value: unknown) {
  if (value === undefined) return []
  if (!Array.isArray(value) || value.length > 64) throw new Error('assets 必须是最多 64 项的数组')
  const ids = new Set<string>()
  const paths = new Set<string>()
  return value.map((candidate, index): SkinAssetDescriptor => {
    const asset = objectValue(candidate, `assets[${index}]`)
    assertKnownKeys(asset, ASSET_KEYS, `assets[${index}]`)
    const id = requiredString(asset.id, `assets[${index}].id`, 48)
    if (!ASSET_ID_PATTERN.test(id) || ids.has(id)) throw new Error(`assets[${index}].id 无效或重复`)
    const path = requiredString(asset.path, `assets[${index}].path`, 160)
    if (!isSafeSkinAssetPath(path) || paths.has(path.toLowerCase())) throw new Error(`assets[${index}].path 不安全或重复`)
    const kind = enumValue(asset.kind, ASSET_KINDS, `assets[${index}].kind`)
    const descriptor = { id, path, kind }
    if (!skinAssetMime(descriptor)) throw new Error(`assets[${index}] 不支持该资源格式`)
    ids.add(id)
    paths.add(path.toLowerCase())
    return descriptor
  })
}

function parseAssetReferences(
  assets: SkinAssetDescriptor[],
  typography: V3SkinTypography,
  icons: V3SkinIcons,
  background?: V3SkinBackground,
  decoration?: V3SkinDecoration
) {
  const byId = new Map(assets.map((asset) => [asset.id, asset]))
  const requireKind = (id: string, kind: SkinAssetKind, label: string) => {
    const asset = byId.get(id)
    if (!asset) throw new Error(`${label}引用了未声明资源 ${id}`)
    if (asset.kind !== kind) throw new Error(`${label}引用的 ${id} 不是 ${kind} 资源`)
  }
  Object.entries(typography.assets || {}).forEach(([role, id]) => requireKind(id, 'font', `typography.assets.${role}`))
  Object.entries(icons.overrides || {}).forEach(([slot, id]) => requireKind(id, 'icon', `icons.overrides.${slot}`))
  if (background) requireKind(background.asset, 'image', 'background.asset')
  if (decoration?.overlay) requireKind(decoration.overlay.asset, 'image', 'decoration.overlay.asset')
}

function parseV3Skin(parsed: Record<string, unknown>): V3DeclarativeSkin {
  assertKnownKeys(parsed, V3_TOP_LEVEL_KEYS, '皮肤文件')
  const identity = parseIdentity(parsed)
  const foundation = enumValue(parsed.foundation, FOUNDATIONS, 'foundation')

  const paletteRaw = parsed.palette === undefined ? {} : objectValue(parsed.palette, 'palette')
  assertKnownKeys(paletteRaw, PALETTE_KEYS, 'palette')
  const palette = compact(Object.fromEntries(Array.from(PALETTE_KEYS).map((key) => [
    key,
    optionalColor(paletteRaw[key], `palette.${key}`)
  ])) as V3SkinPalette)

  const typographyRaw = parsed.typography === undefined ? {} : objectValue(parsed.typography, 'typography')
  assertKnownKeys(typographyRaw, TYPOGRAPHY_KEYS, 'typography')
  const typographyAssetsRaw = typographyRaw.assets === undefined ? {} : objectValue(typographyRaw.assets, 'typography.assets')
  assertKnownKeys(typographyAssetsRaw, TYPOGRAPHY_ASSET_KEYS, 'typography.assets')
  const typographyAssets = compact(Object.fromEntries(Array.from(TYPOGRAPHY_ASSET_KEYS).map((role) => [
    role,
    typographyAssetsRaw[role] === undefined ? undefined : requiredString(typographyAssetsRaw[role], `typography.assets.${role}`, 48)
  ])) as Partial<Record<SkinFontRole, string>>)
  const typography: V3SkinTypography = compact({
    preset: enumValue(typographyRaw.preset, TYPOGRAPHY_PRESETS, 'typography.preset', 'system'),
    scale: optionalNumber(typographyRaw.scale, 'typography.scale', 0.8, 1.3),
    assets: Object.keys(typographyAssets).length ? typographyAssets : undefined
  })

  const materialRaw = parsed.material === undefined ? {} : objectValue(parsed.material, 'material')
  assertKnownKeys(materialRaw, MATERIAL_KEYS, 'material')
  const material: V3SkinMaterial = compact({
    preset: enumValue(materialRaw.preset, MATERIAL_PRESETS, 'material.preset', 'flat'),
    strength: optionalNumber(materialRaw.strength, 'material.strength', 0, 1),
    elevation: optionalNumber(materialRaw.elevation, 'material.elevation', 0, 1),
    innerHighlight: optionalNumber(materialRaw.innerHighlight, 'material.innerHighlight', 0, 1),
    grain: optionalNumber(materialRaw.grain, 'material.grain', 0, 1),
    buttonDepth: optionalNumber(materialRaw.buttonDepth, 'material.buttonDepth', 0, 8)
  })

  const geometryRaw = parsed.geometry === undefined ? {} : objectValue(parsed.geometry, 'geometry')
  assertKnownKeys(geometryRaw, GEOMETRY_KEYS, 'geometry')
  const geometry: V3SkinGeometry = compact({
    lineWidth: optionalNumber(geometryRaw.lineWidth, 'geometry.lineWidth', 1, 4),
    panelRadius: optionalNumber(geometryRaw.panelRadius, 'geometry.panelRadius', 0, 32),
    bubbleRadius: optionalNumber(geometryRaw.bubbleRadius, 'geometry.bubbleRadius', 0, 32),
    buttonRadius: optionalNumber(geometryRaw.buttonRadius, 'geometry.buttonRadius', 0, 24),
    edgeProfile: geometryRaw.edgeProfile === undefined
      ? undefined
      : enumValue(geometryRaw.edgeProfile, EDGE_PROFILES, 'geometry.edgeProfile')
  })

  const componentsRaw = parsed.components === undefined ? {} : objectValue(parsed.components, 'components')
  assertKnownKeys(componentsRaw, COMPONENT_KEYS, 'components')
  const components: V3SkinComponents = {
    chrome: enumValue(componentsRaw.chrome, CHROME_PRESETS, 'components.chrome', 'none'),
    messages: enumValue(componentsRaw.messages, MESSAGE_PRESETS, 'components.messages', 'bubbles'),
    tools: enumValue(componentsRaw.tools, TOOL_PRESETS, 'components.tools', 'card'),
    context: enumValue(componentsRaw.context, CONTEXT_PRESETS, 'components.context', 'bar'),
    fileTree: enumValue(componentsRaw.fileTree, FILE_TREE_PRESETS, 'components.fileTree', 'standard')
  }

  const iconsRaw = parsed.icons === undefined ? {} : objectValue(parsed.icons, 'icons')
  assertKnownKeys(iconsRaw, ICON_KEYS, 'icons')
  const iconOverridesRaw = iconsRaw.overrides === undefined ? {} : objectValue(iconsRaw.overrides, 'icons.overrides')
  const unknownIconSlots = Object.keys(iconOverridesRaw).filter((slot) => !ICON_SLOTS.has(slot as SkinIconSlot))
  if (unknownIconSlots.length) throw new Error(`icons.overrides 包含不支持的图标槽位：${unknownIconSlots.join(', ')}`)
  const iconOverrides = compact(Object.fromEntries(Object.entries(iconOverridesRaw).map(([slot, id]) => [
    slot,
    requiredString(id, `icons.overrides.${slot}`, 48)
  ])) as Partial<Record<SkinIconSlot, string>>)
  const icons: V3SkinIcons = compact({
    preset: enumValue(iconsRaw.preset, ICON_PRESETS, 'icons.preset', 'default'),
    overrides: Object.keys(iconOverrides).length ? iconOverrides : undefined
  })

  let background: V3SkinBackground | undefined
  if (parsed.background !== undefined) {
    const backgroundRaw = objectValue(parsed.background, 'background')
    assertKnownKeys(backgroundRaw, BACKGROUND_KEYS, 'background')
    background = compact({
      asset: requiredString(backgroundRaw.asset, 'background.asset', 48),
      fit: backgroundRaw.fit === undefined ? undefined : enumValue(backgroundRaw.fit, BACKGROUND_FITS, 'background.fit'),
      position: backgroundRaw.position === undefined ? undefined : enumValue(backgroundRaw.position, BACKGROUND_POSITIONS, 'background.position'),
      opacity: optionalNumber(backgroundRaw.opacity, 'background.opacity', 0, 1),
      overlay: optionalColor(backgroundRaw.overlay, 'background.overlay'),
      overlayOpacity: optionalNumber(backgroundRaw.overlayOpacity, 'background.overlayOpacity', 0, 1),
      blur: optionalNumber(backgroundRaw.blur, 'background.blur', 0, 24)
    })
  }

  const effectsRaw = parsed.effects === undefined ? {} : objectValue(parsed.effects, 'effects')
  assertKnownKeys(effectsRaw, EFFECT_KEYS, 'effects')
  if (effectsRaw.layers !== undefined && effectsRaw.preset !== undefined) {
    throw new Error('effects.layers 与 effects.preset 不能同时声明')
  }
  const effectLayers = parseEffectLayers(effectsRaw.layers)
  const effects: V3SkinEffects = compact({
    preset: effectLayers ? undefined : enumValue(effectsRaw.preset, EFFECT_PRESETS, 'effects.preset', 'none'),
    layers: effectLayers,
    intensity: optionalNumber(effectsRaw.intensity, 'effects.intensity', 0, 1),
    motion: effectsRaw.motion === undefined ? undefined : enumValue(effectsRaw.motion, MOTION_PRESETS, 'effects.motion')
  })

  const decorationRaw = parsed.decoration === undefined ? {} : objectValue(parsed.decoration, 'decoration')
  assertKnownKeys(decorationRaw, DECORATION_KEYS, 'decoration')
  let decorationOverlay: V3SkinDecorationOverlay | undefined
  if (decorationRaw.overlay !== undefined) {
    const overlayRaw = objectValue(decorationRaw.overlay, 'decoration.overlay')
    assertKnownKeys(overlayRaw, DECORATION_OVERLAY_KEYS, 'decoration.overlay')
    decorationOverlay = compact({
      asset: requiredString(overlayRaw.asset, 'decoration.overlay.asset', 48),
      fit: overlayRaw.fit === undefined ? undefined : enumValue(overlayRaw.fit, BACKGROUND_FITS, 'decoration.overlay.fit'),
      position: overlayRaw.position === undefined ? undefined : enumValue(overlayRaw.position, BACKGROUND_POSITIONS, 'decoration.overlay.position'),
      opacity: optionalNumber(overlayRaw.opacity, 'decoration.overlay.opacity', 0, 0.65)
    })
  }
  const decoration: V3SkinDecoration = compact({
    preset: enumValue(decorationRaw.preset, DECORATION_PRESETS, 'decoration.preset', 'none'),
    density: optionalNumber(decorationRaw.density, 'decoration.density', 0, 1),
    overlay: decorationOverlay
  })
  const assets = parseAssets(parsed.assets)
  parseAssetReferences(assets, typography, icons, background, decoration)

  if (!Object.keys(palette).length && material.preset === 'flat' && components.chrome === 'none'
    && getSkinEffectLayers(effects).length === 0 && decoration.preset === 'none' && icons.preset === 'default'
    && typography.preset === 'system' && !background && !decoration.overlay) {
    throw new Error('v3 皮肤至少需要一个视觉积木')
  }

  return {
    schema: CUSTOM_SKIN_SCHEMA,
    ...identity,
    foundation,
    palette,
    typography,
    material,
    geometry,
    components,
    icons,
    background,
    effects,
    decoration,
    assets
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
  if (parsed.schema === CUSTOM_SKIN_SCHEMA) return parseV3Skin(parsed)
  if (parsed.schema === CUSTOM_SKIN_SCHEMA_V1 || parsed.schema === CUSTOM_SKIN_SCHEMA_V2) {
    return parseLegacySkin(parsed, parsed.schema)
  }
  throw new Error(`schema 必须是 ${CUSTOM_SKIN_SCHEMA_V1}、${CUSTOM_SKIN_SCHEMA_V2} 或 ${CUSTOM_SKIN_SCHEMA}`)
}

export function isV3Skin(skin: DeclarativeSkin): skin is V3DeclarativeSkin {
  return skin.schema === CUSTOM_SKIN_SCHEMA
}

export function isLegacySkin(skin: DeclarativeSkin): skin is LegacyDeclarativeSkin {
  return !isV3Skin(skin)
}

export function getSkinFoundationTheme(skin: DeclarativeSkin): ThemeId {
  if (!isV3Skin(skin)) return skin.baseTheme
  return skin.foundation === 'light' ? 'paper' : 'lab'
}

export function getSkinChromePreset(skin: DeclarativeSkin): V3ChromePreset {
  if (isV3Skin(skin)) return skin.components.chrome
  return skin.chrome?.type === 'hud' ? 'hud' : 'none'
}

export function skinUsesChrome(skin: DeclarativeSkin) {
  return getSkinChromePreset(skin) !== 'none'
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

function buildLegacyVariables(skin: LegacyDeclarativeSkin): Record<string, string> {
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
  if (skin.tokens.panelOpacity !== undefined) variables['--neon-panel-glass'] = rgba(surface, skin.tokens.panelOpacity)
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
  if (skin.geometry?.panelRadius !== undefined) variables['--custom-skin-panel-radius'] = `${skin.geometry.panelRadius}px`
  if (skin.geometry?.bubbleRadius !== undefined) variables['--custom-skin-bubble-radius'] = `${skin.geometry.bubbleRadius}px`
  if (skin.geometry?.buttonRadius !== undefined) variables['--custom-skin-button-radius'] = `${skin.geometry.buttonRadius}px`
  if (skin.decoration) variables['--custom-skin-decoration-density'] = String(skin.decoration.density ?? 0.3)
  variables['--custom-skin-glow'] = String(glow)
  return variables
}

function buildV3Variables(skin: V3DeclarativeSkin): Record<string, string> {
  const variables: Record<string, string> = {}
  const paletteMap: Array<[keyof V3SkinPalette, string]> = [
    ['accent', '--skin-color-accent'], ['accentAlt', '--skin-color-accent-alt'],
    ['background', '--skin-color-background'], ['surface', '--skin-color-surface'],
    ['surfaceRaised', '--skin-color-surface-raised'], ['text', '--skin-color-text'],
    ['textMuted', '--skin-color-text-muted'], ['border', '--skin-color-border'],
    ['success', '--skin-color-success'], ['warning', '--skin-color-warning'],
    ['danger', '--skin-color-danger'], ['selection', '--skin-color-selection']
  ]
  paletteMap.forEach(([key, variable]) => {
    const value = skin.palette[key]
    if (value) variables[variable] = value
  })
  if (skin.palette.accent) {
    variables['--color-primary'] = skin.palette.accent
    variables['--color-primary-hover'] = skin.palette.accent
    variables['--color-primary-container'] = rgba(skin.palette.accent, 0.16)
    variables['--color-primary-border'] = rgba(skin.palette.accent, 0.48)
    variables['--color-primary-soft'] = rgba(skin.palette.accent, 0.09)
    variables['--color-primary-glow'] = rgba(skin.palette.accent, skin.effects.intensity ?? 0.35)
  }
  if (skin.palette.background) {
    variables['--theme-app-background'] = skin.palette.background
    variables['--color-surface-container-lowest'] = skin.palette.background
  }
  if (skin.palette.surface) {
    variables['--color-surface-container-low'] = skin.palette.surface
    variables['--color-surface-container'] = skin.palette.surface
  }
  if (skin.palette.surfaceRaised) {
    variables['--color-surface-container-high'] = skin.palette.surfaceRaised
    variables['--color-surface-container-highest'] = skin.palette.surfaceRaised
  }
  if (skin.palette.text) variables['--color-on-surface'] = skin.palette.text
  if (skin.palette.textMuted) variables['--color-on-surface-variant'] = skin.palette.textMuted
  if (skin.palette.success) variables['--color-success'] = skin.palette.success
  if (skin.palette.warning) variables['--color-warning'] = skin.palette.warning
  if (skin.palette.danger) variables['--color-danger'] = skin.palette.danger

  if (skin.geometry.lineWidth !== undefined) {
    variables['--skin-line-width'] = `${skin.geometry.lineWidth}px`
    variables['--custom-skin-line-width'] = `${skin.geometry.lineWidth}px`
  }
  if (skin.geometry.panelRadius !== undefined) {
    variables['--skin-panel-radius'] = `${skin.geometry.panelRadius}px`
    variables['--custom-skin-panel-radius'] = `${skin.geometry.panelRadius}px`
  }
  if (skin.geometry.bubbleRadius !== undefined) {
    variables['--skin-bubble-radius'] = `${skin.geometry.bubbleRadius}px`
    variables['--custom-skin-bubble-radius'] = `${skin.geometry.bubbleRadius}px`
  }
  if (skin.geometry.buttonRadius !== undefined) {
    variables['--skin-button-radius'] = `${skin.geometry.buttonRadius}px`
    variables['--custom-skin-button-radius'] = `${skin.geometry.buttonRadius}px`
  }
  variables['--skin-typography-scale'] = String(skin.typography.scale ?? 1)
  variables['--skin-material-strength'] = String(skin.material.strength ?? 0.65)
  variables['--skin-material-elevation'] = String(skin.material.elevation ?? 0.5)
  variables['--skin-material-highlight'] = String(skin.material.innerHighlight ?? 0.55)
  variables['--skin-material-grain'] = String(skin.material.grain ?? 0.12)
  variables['--skin-button-depth'] = `${skin.material.buttonDepth ?? 2}px`
  variables['--skin-effect-intensity'] = String(skin.effects.intensity ?? 0.35)
  variables['--skin-decoration-density'] = String(skin.decoration.density ?? 0.3)
  if (skin.decoration.overlay) {
    variables['--skin-decoration-overlay-fit'] = skin.decoration.overlay.fit === 'tile'
      ? 'auto'
      : (skin.decoration.overlay.fit ?? 'contain')
    variables['--skin-decoration-overlay-repeat'] = skin.decoration.overlay.fit === 'tile' ? 'repeat' : 'no-repeat'
    variables['--skin-decoration-overlay-position'] = skin.decoration.overlay.position ?? 'center'
    variables['--skin-decoration-overlay-opacity'] = String(skin.decoration.overlay.opacity ?? 0.3)
  }
  if (skin.background) {
    variables['--skin-background-fit'] = skin.background.fit === 'tile' ? 'auto' : (skin.background.fit ?? 'cover')
    variables['--skin-background-repeat'] = skin.background.fit === 'tile' ? 'repeat' : 'no-repeat'
    variables['--skin-background-position'] = skin.background.position ?? 'center'
    variables['--skin-background-opacity'] = String(skin.background.opacity ?? 0.45)
    variables['--skin-background-overlay'] = skin.background.overlay ?? '#000000'
    variables['--skin-background-overlay-opacity'] = String(skin.background.overlayOpacity ?? 0.35)
    variables['--skin-background-blur'] = `${skin.background.blur ?? 0}px`
  }
  return variables
}

export function buildCustomSkinVariables(skin: DeclarativeSkin): Record<string, string> {
  return isV3Skin(skin) ? buildV3Variables(skin) : buildLegacyVariables(skin)
}

const CUSTOM_PROPERTIES = [
  '--color-primary', '--color-primary-hover', '--color-primary-container', '--color-primary-border',
  '--color-primary-soft', '--color-primary-glow', '--color-success', '--color-warning', '--color-danger',
  '--color-surface-container-lowest', '--color-surface-container-low', '--color-surface-container',
  '--color-surface-container-high', '--color-surface-container-highest', '--color-on-surface',
  '--color-on-surface-variant', '--theme-app-background', '--neon-hologram-edge', '--neon-panel-edge',
  '--neon-panel-glass', '--neon-line-width', '--neon-content-radius', '--custom-skin-line-width',
  '--custom-skin-radius', '--custom-skin-glow', '--custom-skin-shadow-y', '--custom-skin-shadow-blur',
  '--custom-skin-shadow-alpha', '--custom-skin-inner-highlight-alpha', '--custom-skin-grain-alpha',
  '--custom-skin-button-depth', '--custom-skin-panel-radius', '--custom-skin-bubble-radius',
  '--custom-skin-button-radius', '--custom-skin-decoration-density', '--skin-color-accent',
  '--skin-color-accent-alt', '--skin-color-background', '--skin-color-surface', '--skin-color-surface-raised',
  '--skin-color-text', '--skin-color-text-muted', '--skin-color-border', '--skin-color-success',
  '--skin-color-warning', '--skin-color-danger', '--skin-color-selection', '--skin-line-width',
  '--skin-panel-radius', '--skin-bubble-radius', '--skin-button-radius', '--skin-typography-scale',
  '--skin-material-strength', '--skin-material-elevation', '--skin-material-highlight', '--skin-material-grain',
  '--skin-button-depth', '--skin-effect-intensity', '--skin-decoration-density', '--skin-background-fit',
  '--skin-background-repeat', '--skin-background-position', '--skin-background-opacity',
  '--skin-background-overlay', '--skin-background-overlay-opacity', '--skin-background-blur',
  '--skin-background-image', '--skin-decoration-overlay-image', '--skin-decoration-overlay-fit',
  '--skin-decoration-overlay-repeat', '--skin-decoration-overlay-position', '--skin-decoration-overlay-opacity',
  '--skin-font-ui', '--skin-font-content', '--skin-font-code', '--skin-font-display',
  ...Array.from(ICON_SLOTS).map((slot) => `--skin-icon-${slot}`)
]

export function skinIconDatasetKey(slot: SkinIconSlot) {
  return `skinIcon${slot.split('-').map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join('')}`
}

export function getSkinEffectLayers(effects: V3SkinEffects): V3ActiveEffectPreset[] {
  if (effects.layers?.length) return effects.layers
  return !effects.preset || effects.preset === 'none' ? [] : [effects.preset]
}

function skinEffectDatasetKey(effect: V3ActiveEffectPreset) {
  return `skinEffect${effect.charAt(0).toUpperCase()}${effect.slice(1)}`
}

const CUSTOM_DATASET_KEYS: string[] = [
  'customSkin', 'customSkinSchema', 'customSkinChrome', 'customSkinPanel', 'customSkinBubble',
  'customSkinMaterial', 'customSkinDecoration', 'skinFoundation', 'skinMaterial', 'skinTypography',
  'skinChrome', 'skinMessages', 'skinTools', 'skinContext', 'skinFileTree', 'skinIcons',
  'skinEffects', 'skinMotion', 'skinDecoration', 'skinEdgeProfile', 'skinHasBackground',
  'skinHasDecorationOverlay', 'skinHasIconAssets',
  ...Array.from(ACTIVE_EFFECT_PRESETS).map(skinEffectDatasetKey),
  ...Array.from(ICON_SLOTS).map(skinIconDatasetKey)
]

export function applyCustomSkinToRoot(root: HTMLElement, state: ActiveCustomSkin | null) {
  CUSTOM_PROPERTIES.forEach((property) => root.style.removeProperty(property))
  CUSTOM_DATASET_KEYS.forEach((key) => delete root.dataset[key])
  if (!state?.enabled) return
  const { skin } = state
  root.dataset.customSkin = skin.id
  if (isV3Skin(skin)) {
    root.dataset.customSkinSchema = 'v3'
    root.dataset.skinFoundation = skin.foundation
    root.dataset.skinMaterial = skin.material.preset
    root.dataset.skinTypography = skin.typography.preset
    root.dataset.skinChrome = skin.components.chrome
    root.dataset.skinMessages = skin.components.messages
    root.dataset.skinTools = skin.components.tools
    root.dataset.skinContext = skin.components.context
    root.dataset.skinFileTree = skin.components.fileTree
    root.dataset.skinIcons = skin.icons.preset
    if (skin.geometry.edgeProfile) root.dataset.skinEdgeProfile = skin.geometry.edgeProfile
    const effectLayers = getSkinEffectLayers(skin.effects)
    root.dataset.skinEffects = effectLayers[0] ?? 'none'
    effectLayers.forEach((effect) => {
      root.dataset[skinEffectDatasetKey(effect)] = 'true'
    })
    root.dataset.skinMotion = skin.effects.motion ?? 'subtle'
    root.dataset.skinDecoration = skin.decoration.preset
    if (skin.background) root.dataset.skinHasBackground = 'pending'
    if (skin.decoration.overlay) root.dataset.skinHasDecorationOverlay = 'pending'
    if (skin.icons.overrides && Object.keys(skin.icons.overrides).length) {
      root.dataset.skinHasIconAssets = 'pending'
    }
  } else {
    if (skin.chrome) {
      root.dataset.customSkinChrome = skin.chrome.type
      root.dataset.customSkinPanel = skin.chrome.panelGeometry || 'stepped'
      root.dataset.customSkinBubble = skin.chrome.bubbleGeometry || 'mirrored'
    }
    if (skin.material) root.dataset.customSkinMaterial = skin.material.preset
    if (skin.decoration) root.dataset.customSkinDecoration = skin.decoration.preset
  }
  Object.entries(buildCustomSkinVariables(skin)).forEach(([property, value]) => root.style.setProperty(property, value))
}
