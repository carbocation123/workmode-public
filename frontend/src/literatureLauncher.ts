import { api, type Project } from './api'
import { LITERATURE_PROJECT_KEY, literatureWorkbenchUrl } from './literatureNavigation'

function basenameFromPath(path: string): string {
  return path.replace(/[\\/]+$/, '').split(/[\\/]/).pop() || '文献智库'
}

export interface LiteratureLaunchOptions {
  projects?: Project[]
  activeProject?: Project | null
  onProjectCreated?: () => void | Promise<void>
  confirmCreate?: (message: string) => boolean
}

export async function prepareLiteratureWorkbench(
  currentHref: string,
  options: LiteratureLaunchOptions = {},
): Promise<string | null> {
  const payload = options.projects
    ? { projects: options.projects }
    : await api.projects()
  const projects = payload.projects
  const rememberedSlug = window.sessionStorage.getItem(LITERATURE_PROJECT_KEY)
  let literatureProject = options.activeProject?.project_type === 'literature-library'
    ? options.activeProject
    : projects.find((project) => project.slug === rememberedSlug && project.project_type === 'literature-library')
      || projects.find((project) => project.project_type === 'literature-library')

  if (!literatureProject) {
    const confirmCreate = options.confirmCreate || ((message: string) => window.confirm(message))
    if (!confirmCreate(
      '还没有文献智库项目。\n\n接下来请选择或新建一个空文件夹，Workmode 会在其中建立固定结构的文献库。',
    )) return null
    const picked = await api.pickDirectory()
    if (!picked.path) return null
    const created = await api.createLiteratureProject({
      name: basenameFromPath(picked.path),
      root_path: picked.path,
    })
    literatureProject = created.project
    await options.onProjectCreated?.()
  }

  await api.setActive(literatureProject.slug)
  window.sessionStorage.setItem(LITERATURE_PROJECT_KEY, literatureProject.slug)
  return literatureWorkbenchUrl(currentHref)
}
