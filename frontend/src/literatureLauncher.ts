import { api, type Project } from './api'
import { LITERATURE_PROJECT_KEY, literatureWorkbenchUrl } from './literatureNavigation'

export interface LiteratureLaunchOptions {
  projects?: Project[]
  activeProject?: Project | null
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
  const literatureProject = options.activeProject?.project_type === 'literature-library'
    ? options.activeProject
    : projects.find((project) => project.slug === rememberedSlug && project.project_type === 'literature-library')
      || projects.find((project) => project.project_type === 'literature-library')

  if (literatureProject) {
    await api.setActive(literatureProject.slug)
    window.sessionStorage.setItem(LITERATURE_PROJECT_KEY, literatureProject.slug)
  } else {
    window.sessionStorage.removeItem(LITERATURE_PROJECT_KEY)
  }
  return literatureWorkbenchUrl(currentHref)
}
