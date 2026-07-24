export type ProjectRefreshTarget = 'tree' | 'papers' | 'tags' | 'groups' | 'notes'

export function projectRefreshTargets(paths: string[]): Set<ProjectRefreshTarget> {
  const targets = new Set<ProjectRefreshTarget>()
  for (const rawPath of paths) {
    const path = rawPath.trim().replace(/\\/g, '/').replace(/^\.\//, '').toLocaleLowerCase()
    if (!path) continue
    targets.add('tree')
    if (path === 'catalog.json' || path.startsWith('papers/')) targets.add('papers')
    if (path === 'tags.json') targets.add('tags')
    if (path === 'groups.json') targets.add('groups')
    if (path.startsWith('notes/')) targets.add('notes')
  }
  return targets
}
