import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'

import { MarkdownRenderer } from './MarkdownRenderer'


describe('MarkdownRenderer', () => {
  it('renders GitHub-flavored pipe tables as semantic HTML tables', () => {
    const markdown = [
      '| Sample | T50 |',
      '|---|---:|',
      '| C450 | 172.7 °C |'
    ].join('\n')

    const html = renderToStaticMarkup(<MarkdownRenderer>{markdown}</MarkdownRenderer>)

    expect(html).toContain('<table>')
    expect(html).toContain('<th>Sample</th>')
    expect(html).toContain('<td>C450</td>')
    expect(html).toContain('text-align:right')
  })
})
