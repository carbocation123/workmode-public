import { describe, expect, it } from 'vitest'
import { toolSemanticLabel, toolStatusSkinIcon } from './skinSemantics'

describe('toolStatusSkinIcon', () => {
  it('maps every persisted tool state to an icon slot declared by the skin protocol', () => {
    expect(toolStatusSkinIcon('running')).toBe('tool-running')
    expect(toolStatusSkinIcon('done')).toBe('tool-done')
    expect(toolStatusSkinIcon('error')).toBe('tool-error')
    expect(toolStatusSkinIcon('cancelled')).toBe('tool-error')
  })

  it('maps called tools to compact semantic labels instead of status glyphs', () => {
    expect(toolSemanticLabel('project_read')).toBe('READ')
    expect(toolSemanticLabel('project_write')).toBe('WRITE')
    expect(toolSemanticLabel('project_python_file')).toBe('PY')
    expect(toolSemanticLabel('web_search')).toBe('WEB')
    expect(toolSemanticLabel('web_fetch')).toBe('FETCH')
    expect(toolSemanticLabel('memory_write')).toBe('MEM')
    expect(toolSemanticLabel('plan_my_steps')).toBe('PLAN')
    expect(toolSemanticLabel('unknown_extension_tool')).toBe('TOOL')
  })
})
