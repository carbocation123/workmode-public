export const THEME_STORAGE_KEY = 'workmode-public-theme-v1'

export type ThemeId = 'lab' | 'origin-ring' | 'neon-space-lab' | 'paper' | 'observatory' | 'high-contrast'
export type ThemeSelection = 'system' | ThemeId

export interface ThemeDefinition {
  id: ThemeId
  name: string
  description: string
  icon: string
  swatches: [string, string, string]
  layout?: 'standard' | 'hud'
  unlockAchievement?: string
  unlockHint?: string
}

export interface ThemePreference {
  version: 1
  selection: ThemeSelection
  reduceMotion: boolean
}

export const THEMES: ThemeDefinition[] = [
  {
    id: 'lab',
    name: '实验室',
    description: '克制、紧凑的默认深色工作台',
    icon: '⌬',
    swatches: ['#0e0f12', '#1a1d23', '#6c9fff']
  },
  {
    id: 'origin-ring',
    name: 'Origin Ring',
    description: '深蓝环形微光与科研仪器质感',
    icon: '◎',
    swatches: ['#040817', '#0d1933', '#54b9ff'],
    unlockAchievement: 'tutorial_graduate',
    unlockHint: '完成科研协作教程后解锁'
  },
  {
    id: 'neon-space-lab',
    name: 'Neon Space Lab',
    description: '完整舰桥 HUD、遥测仪表与青蓝扫描光',
    icon: '⌬',
    swatches: ['#02060b', '#071c2a', '#43e8ff'],
    layout: 'hud',
    unlockAchievement: 'tutorial_graduate',
    unlockHint: '完成科研协作教程后解锁'
  },
  {
    id: 'paper',
    name: '论文纸',
    description: '暖白纸张与低饱和学术蓝',
    icon: '▤',
    swatches: ['#f3efe6', '#fffdf8', '#315f8a']
  },
  {
    id: 'observatory',
    name: '深夜观测站',
    description: '低亮度深空背景，适合夜间工作',
    icon: '◐',
    swatches: ['#070914', '#12162a', '#8fa7ff']
  },
  {
    id: 'high-contrast',
    name: '高对比',
    description: '清晰边界、明亮焦点与最大可读性',
    icon: '◩',
    swatches: ['#000000', '#111111', '#ffe600']
  }
]

export const DEFAULT_THEME_PREFERENCE: ThemePreference = {
  version: 1,
  selection: 'lab',
  reduceMotion: false
}

const THEME_SELECTIONS = new Set<ThemeSelection>(['system', ...THEMES.map((theme) => theme.id)])

export function parseThemePreference(raw: string | null): ThemePreference {
  if (!raw) return { ...DEFAULT_THEME_PREFERENCE }
  try {
    const parsed = JSON.parse(raw) as Partial<ThemePreference>
    if (parsed.version !== 1 || !THEME_SELECTIONS.has(parsed.selection as ThemeSelection)) {
      return { ...DEFAULT_THEME_PREFERENCE }
    }
    return {
      version: 1,
      selection: parsed.selection as ThemeSelection,
      reduceMotion: typeof parsed.reduceMotion === 'boolean' ? parsed.reduceMotion : false
    }
  } catch {
    return { ...DEFAULT_THEME_PREFERENCE }
  }
}

export function resolveTheme(selection: ThemeSelection, prefersDark: boolean): ThemeId {
  if (selection === 'system') return prefersDark ? 'observatory' : 'paper'
  return selection
}

export function themeIsUnlocked(theme: ThemeDefinition, achievements: Record<string, string>): boolean {
  return !theme.unlockAchievement || Boolean(achievements[theme.unlockAchievement])
}

export function allowedThemeSelection(
  selection: ThemeSelection,
  achievements: Record<string, string>
): ThemeSelection {
  if (selection === 'system') return selection
  const theme = THEMES.find((item) => item.id === selection)
  return theme && themeIsUnlocked(theme, achievements) ? selection : 'lab'
}

export function applyThemeToRoot(root: HTMLElement, preference: ThemePreference, prefersDark: boolean) {
  root.dataset.theme = resolveTheme(preference.selection, prefersDark)
  root.dataset.reducedMotion = preference.reduceMotion ? 'true' : 'false'
}
