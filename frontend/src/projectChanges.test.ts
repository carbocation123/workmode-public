import { describe, expect, it } from 'vitest'

import { projectRefreshTargets } from './projectChanges'

describe('projectRefreshTargets', () => {
  it('maps authoritative literature files to the projections that must be reloaded', () => {
    expect(projectRefreshTargets(['catalog.json'])).toEqual(new Set(['papers', 'tree']))
    expect(projectRefreshTargets(['tags.json'])).toEqual(new Set(['tags', 'tree']))
    expect(projectRefreshTargets(['notes/discussion.md'])).toEqual(new Set(['notes', 'tree']))
  })

  it('coalesces mixed tool writes without losing the generic project tree refresh', () => {
    expect(projectRefreshTargets([
      'catalog.json',
      'tags.json',
      'notes/discussion.md',
      'papers/unprocessed/extracted/paper-1/objective-facts.md',
    ])).toEqual(new Set(['papers', 'tags', 'notes', 'tree']))
  })
})
