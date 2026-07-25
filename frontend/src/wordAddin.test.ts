import { readFileSync } from 'node:fs'
import { describe, expect, it } from 'vitest'

const decode = (url: URL) => new TextDecoder().decode(readFileSync(url))
const manifest = decode(new URL('../word-addin/manifest.xml', import.meta.url))
const commands = decode(new URL('../word-addin/commands.ts', import.meta.url))
const dialog = decode(new URL('../word-addin/dialog.ts', import.meta.url))
const dialogHtml = decode(new URL('../word-addin/dialog.html', import.meta.url))
const vite = decode(new URL('../vite.config.ts', import.meta.url))
const installScript = decode(new URL('../../scripts/install-word-addin.ps1', import.meta.url))
const uninstallScript = decode(new URL('../../scripts/uninstall-word-addin.ps1', import.meta.url))

describe('Word ribbon add-in contract', () => {
  it('adds one Workmode ribbon tab without a permanent task pane', () => {
    expect(manifest).toContain('<CustomTab id="Workmode.Tab">')
    expect(manifest).toContain('resid="Workmode.Tab.Label"')
    expect(manifest).toContain('resid="Workmode.InsertCitation.Label"')
    expect(manifest).toContain('resid="Workmode.EditCitation.Label"')
    expect(manifest).toContain('resid="Workmode.Refresh.Label"')
    expect(manifest).toContain('resid="Workmode.Bibliography.Label"')
    expect(manifest).toContain('resid="Workmode.Style.Label"')
    expect(manifest).not.toContain('<ShowTaskpane>')
    expect(manifest).toContain('http://localhost:8765/word-addin/commands.html')
  })

  it('opens a transient citation dialog and completes every ribbon command', () => {
    expect(commands).toContain('Office.context.ui.displayDialogAsync')
    expect(commands).toContain('/word-addin/citations/refresh')
    expect(commands).toContain('/word-addin/bibliography')
    expect(commands).toContain('event.completed()')
    expect(commands).toContain('Office.actions.associate')
  })

  it('searches, inserts, edits and removes citations from inside Word', () => {
    expect(dialogHtml).toContain('搜索 Workmode 文献')
    expect(dialog).toContain('/word-addin/bootstrap')
    expect(dialog).toContain('/word-addin/papers')
    expect(dialog).toContain('/word-addin/citations')
    expect(dialog).toContain('/word-addin/citations/inspect')
    expect(dialog).toContain('/word-addin/citations/update')
    expect(dialog).toContain('/word-addin/citations/remove')
  })

  it('ships the add-in pages and reversible per-user Word registration', () => {
    expect(vite).toContain("wordAddinCommands: 'word-addin/commands.html'")
    expect(vite).toContain("wordAddinDialog: 'word-addin/dialog.html'")
    expect(installScript).toContain('Software\\Microsoft\\Office\\16.0\\WEF\\Developer')
    expect(installScript).toContain('manifest.xml')
    expect(uninstallScript).toContain('Remove-ItemProperty')
  })
})
