export const RUNTIME_API_BASE_KEY = 'workmode-public-api-base'
export const LITERATURE_PROJECT_KEY = 'workmode-public-literature-project'
export type ApplicationSurface = 'home' | 'workbench'
export type WorkbenchPanel = 'project' | 'settings'
export type SettingsReturnSurface = 'literature' | null

export function literatureWorkbenchUrl(currentHref: string): string {
  return new URL('./literature/index.html', currentHref).toString()
}

export function applicationHomeUrl(currentHref: string): string {
  const url = new URL('../index.html', currentHref)
  url.search = ''
  url.hash = ''
  return url.toString()
}

export function workbenchUrl(currentHref: string): string {
  const url = new URL('../index.html', currentHref)
  url.search = ''
  url.searchParams.set('surface', 'workbench')
  url.hash = ''
  return url.toString()
}

export function workbenchSettingsUrl(
  currentHref: string,
  returnSurface: SettingsReturnSurface = null,
): string {
  const url = new URL('../index.html', currentHref)
  url.search = ''
  url.searchParams.set('surface', 'workbench')
  url.searchParams.set('panel', 'settings')
  if (returnSurface) url.searchParams.set('return', returnSurface)
  url.hash = ''
  return url.toString()
}

export function resolveApplicationSurface(currentHref: string): ApplicationSurface {
  return new URL(currentHref).searchParams.get('surface') === 'workbench' ? 'workbench' : 'home'
}

export function resolveWorkbenchPanel(currentHref: string): WorkbenchPanel {
  return new URL(currentHref).searchParams.get('panel') === 'settings' ? 'settings' : 'project'
}

export function resolveSettingsReturnSurface(currentHref: string): SettingsReturnSurface {
  return new URL(currentHref).searchParams.get('return') === 'literature' ? 'literature' : null
}
