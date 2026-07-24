import { describe, expect, it } from 'vitest'

import { resolveButtonTooltip } from './buttonTooltips'

describe('literature button tooltips', () => {
  it('prefers an explicit tooltip over accessibility and visible labels', () => {
    expect(resolveButtonTooltip({
      explicit: '打开项目管理',
      ariaLabel: '管理项目',
      text: '项目',
    })).toBe('打开项目管理')
  })

  it('uses the accessibility label for icon-only buttons', () => {
    expect(resolveButtonTooltip({
      explicit: '',
      ariaLabel: '关闭文献详情',
      text: '',
    })).toBe('关闭文献详情')
  })

  it('normalizes visible button copy as the default tooltip', () => {
    expect(resolveButtonTooltip({
      explicit: '',
      ariaLabel: '',
      text: '  导入\n  EndNote  ',
    })).toBe('导入 EndNote')
  })
})
