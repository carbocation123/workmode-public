import type { ToolRunStatus } from './conversation'
import type { SkinIconSlot } from './customSkin'

export function toolStatusSkinIcon(status: ToolRunStatus): SkinIconSlot {
  if (status === 'running') return 'tool-running'
  if (status === 'done') return 'tool-done'
  return 'tool-error'
}

export function toolSemanticLabel(toolName: string): string {
  const normalized = toolName.trim().toLowerCase()
  if (normalized.startsWith('memory_')) return 'MEM'
  if (normalized === 'plan_my_steps') return 'PLAN'
  if (normalized === 'mark_step_done') return 'STEP'
  if (normalized === 'web_search') return 'WEB'
  if (normalized === 'web_fetch') return 'FETCH'
  if (normalized.includes('python')) return 'PY'
  if (normalized.includes('bash') || normalized.includes('shell')) return 'BASH'
  if (normalized.includes('write')) return 'WRITE'
  if (normalized.includes('edit')) return 'EDIT'
  if (normalized.includes('read')) return 'READ'
  if (normalized.includes('grep')) return 'GREP'
  if (normalized.includes('glob')) return 'GLOB'
  if (normalized.includes('list') || normalized.includes('tree')) return 'LIST'
  return 'TOOL'
}
