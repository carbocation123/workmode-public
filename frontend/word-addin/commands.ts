declare const Office: any

const API = '/api'
const STYLE_KEY = 'workmode-word-style'
const TOKEN_KEY = 'workmode-public-token'
const DIALOG_URL = 'http://localhost:8765/word-addin/dialog.html'

type CommandEvent = { completed: () => void }

function styleId(): string {
  return localStorage.getItem(STYLE_KEY) || 'gb-t-7714-2015-numeric'
}

function headers(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_KEY) || ''
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'X-Workmode-Token': token } : {}),
  }
}

function openDialog(mode: 'insert' | 'edit' | 'status', message = ''): void {
  const query = new URLSearchParams({ mode })
  if (message) query.set('message', message)
  Office.context.ui.displayDialogAsync(
    `${DIALOG_URL}?${query.toString()}`,
    { height: mode === 'status' ? 26 : 72, width: mode === 'status' ? 35 : 58 },
    (result: any) => {
      if (result.status !== Office.AsyncResultStatus.Succeeded) return
      result.value.addEventHandler(
        Office.EventType.DialogMessageReceived,
        (event: { message: string }) => {
          if (event.message === 'close') result.value.close()
        },
      )
    },
  )
}

async function runAction(path: string, event: CommandEvent, nextStyle?: string): Promise<void> {
  try {
    if (nextStyle) localStorage.setItem(STYLE_KEY, nextStyle)
    const response = await fetch(`${API}${path}`, {
      method: 'POST',
      headers: headers(),
      body: JSON.stringify({ style_id: nextStyle || styleId() }),
    })
    const payload = await response.json().catch(() => ({}))
    if (!response.ok) throw new Error(payload.detail || `请求失败（${response.status}）`)
    const message = path.includes('bibliography')
      ? `参考文献已更新：${payload.reference_count ?? 0} 条`
      : `引文已刷新：${payload.citation_count ?? 0} 处`
    openDialog('status', message)
  } catch (error) {
    openDialog('status', error instanceof Error ? error.message : '操作失败，请确认 Workmode 正在运行。')
  } finally {
    event.completed()
  }
}

function insertCitation(event: CommandEvent): void {
  openDialog('insert')
  event.completed()
}

function editCitations(event: CommandEvent): void {
  openDialog('edit')
  event.completed()
}

function refreshCitations(event: CommandEvent): void {
  void runAction('/word-addin/citations/refresh', event)
}

function createBibliography(event: CommandEvent): void {
  void runAction('/word-addin/bibliography', event)
}

function setStyle(style: string, event: CommandEvent): void {
  void runAction('/word-addin/citations/refresh', event, style)
}

Office.onReady(() => {
  Office.actions.associate('insertCitation', insertCitation)
  Office.actions.associate('editCitations', editCitations)
  Office.actions.associate('refreshCitations', refreshCitations)
  Office.actions.associate('createBibliography', createBibliography)
  Office.actions.associate('setStyleGBT', (event: CommandEvent) => setStyle('gb-t-7714-2015-numeric', event))
  Office.actions.associate('setStyleACS', (event: CommandEvent) => setStyle('american-chemical-society', event))
  Office.actions.associate('setStyleNature', (event: CommandEvent) => setStyle('nature', event))
  Office.actions.associate('setStyleAPA', (event: CommandEvent) => setStyle('apa-7th', event))
  Office.actions.associate('setStyleVancouver', (event: CommandEvent) => setStyle('vancouver', event))
})
