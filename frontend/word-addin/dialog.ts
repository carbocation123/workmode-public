declare const Office: any

const API = '/api'
const STYLE_KEY = 'workmode-word-style'
const TOKEN_KEY = 'workmode-public-token'
const params = new URLSearchParams(location.search)
const mode = params.get('mode') || 'insert'

type Paper = {
  id: string
  title: string
  authors: string
  journal: string
  year: number | string | null
  doi: string
  tags: string[]
  groups: string[]
}

type CitationGroup = {
  instance_id: string
  text: string
  items: Array<{ paper_id: string; metadata: Record<string, unknown> }>
}

const selected = new Set<string>()
let papers: Paper[] = []
let editingInstanceId = ''
let searchTimer = 0

function element<T extends HTMLElement>(id: string): T {
  const found = document.getElementById(id)
  if (!found) throw new Error(`Missing element: ${id}`)
  return found as T
}

function apiHeaders(): Record<string, string> {
  const token = localStorage.getItem(TOKEN_KEY) || ''
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'X-Workmode-Token': token } : {}),
  }
}

async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API}${path}`, {
    ...init,
    headers: { ...apiHeaders(), ...(init?.headers || {}) },
  })
  const payload = await response.json().catch(() => ({}))
  if (!response.ok) {
    if (response.status === 401) {
      throw new Error('Workmode 要求连接口令，请在页面底部填写后重新连接。')
    }
    throw new Error(payload.detail || `请求失败（${response.status}）`)
  }
  return payload as T
}

function setMessage(message: string, error = false): void {
  const target = element<HTMLParagraphElement>('message')
  target.textContent = message
  target.style.color = error ? '#ff9b9b' : '#f6ce73'
}

function updateSelection(): void {
  element('selected-count').textContent = String(selected.size)
  element<HTMLButtonElement>('insert').disabled = selected.size === 0
  document.querySelectorAll<HTMLElement>('[data-paper-id]').forEach((card) => {
    const checked = selected.has(card.dataset.paperId || '')
    card.classList.toggle('selected', checked)
    const input = card.querySelector<HTMLInputElement>('input')
    if (input) input.checked = checked
  })
}

function renderPapers(): void {
  const list = element('papers')
  list.replaceChildren()
  if (!papers.length) {
    const empty = document.createElement('p')
    empty.textContent = '没有找到匹配文献，换一个关键词试试。'
    list.append(empty)
    return
  }
  for (const paper of papers) {
    const card = document.createElement('label')
    card.className = 'paper'
    card.dataset.paperId = paper.id
    const checkbox = document.createElement('input')
    checkbox.type = 'checkbox'
    checkbox.addEventListener('change', () => {
      if (checkbox.checked) selected.add(paper.id)
      else selected.delete(paper.id)
      updateSelection()
    })
    const content = document.createElement('span')
    const title = document.createElement('strong')
    title.textContent = paper.title
    const meta = document.createElement('small')
    meta.textContent = [
      paper.authors,
      paper.journal,
      paper.year,
      paper.groups.join(' · '),
      paper.tags.join(' · '),
    ]
      .filter(Boolean)
      .join(' ｜ ')
    content.append(title, meta)
    card.append(checkbox, content)
    list.append(card)
  }
  updateSelection()
}

async function searchPapers(): Promise<void> {
  const query = element<HTMLInputElement>('search').value.trim()
  try {
    setMessage('正在搜索…')
    const result = await api<{ papers: Paper[] }>(
      `/word-addin/papers?query=${encodeURIComponent(query)}&limit=50`,
    )
    papers = result.papers
    renderPapers()
    setMessage(`找到 ${papers.length} 篇文献`)
  } catch (error) {
    setMessage(error instanceof Error ? error.message : '搜索失败', true)
  }
}

function citationBody(): Record<string, unknown> {
  const locatorValue = element<HTMLInputElement>('locator-value').value.trim()
  return {
    paper_ids: [...selected],
    style_id: element<HTMLSelectElement>('style').value,
    prefix: element<HTMLInputElement>('prefix').value,
    suffix: element<HTMLInputElement>('suffix').value,
    locator_label: locatorValue ? element<HTMLSelectElement>('locator-label').value : null,
    locator_value: locatorValue,
    suppress_author: element<HTMLInputElement>('suppress-author').checked,
  }
}

async function submitCitation(): Promise<void> {
  const button = element<HTMLButtonElement>('insert')
  button.disabled = true
  try {
    const style = element<HTMLSelectElement>('style').value
    localStorage.setItem(STYLE_KEY, style)
    const body = {
      ...citationBody(),
      ...(editingInstanceId ? { instance_id: editingInstanceId } : {}),
    }
    const path = editingInstanceId
      ? '/word-addin/citations/update'
      : '/word-addin/citations'
    const result = await api<{ document_name: string; citation_count: number }>(path, {
      method: 'POST',
      body: JSON.stringify(body),
    })
    setMessage(
      editingInstanceId
        ? `引文已更新；当前文档共 ${result.citation_count} 处引用。`
        : `已插入到「${result.document_name}」；当前文档共 ${result.citation_count} 处引用。`,
    )
    editingInstanceId = ''
    selected.clear()
    button.textContent = '插入所选文献'
    updateSelection()
    await loadInspection()
  } catch (error) {
    setMessage(error instanceof Error ? error.message : '插入失败', true)
    updateSelection()
  }
}

async function removeCitation(group: CitationGroup): Promise<void> {
  if (!confirm(`确定从当前文档移除引文 ${group.text || group.instance_id} 吗？`)) return
  try {
    await api('/word-addin/citations/remove', {
      method: 'POST',
      body: JSON.stringify({
        instance_id: group.instance_id,
        style_id: element<HTMLSelectElement>('style').value,
      }),
    })
    setMessage('引文已移除，其他引文和参考文献已重新编号。')
    await loadInspection()
  } catch (error) {
    setMessage(error instanceof Error ? error.message : '移除失败', true)
  }
}

function startReplacing(group: CitationGroup): void {
  editingInstanceId = group.instance_id
  selected.clear()
  for (const item of group.items) selected.add(item.paper_id)
  const button = element<HTMLButtonElement>('insert')
  button.textContent = `更新引文 ${group.text || ''}`
  element<HTMLInputElement>('search').focus()
  updateSelection()
  setMessage('选择新的文献组合，然后点击“更新引文”。')
}

async function loadInspection(): Promise<void> {
  const container = element('citation-groups')
  try {
    const result = await api<{ citation_groups: CitationGroup[]; style_id: string }>(
      '/word-addin/citations/inspect',
    )
    if (result.style_id) {
      element<HTMLSelectElement>('style').value = result.style_id
      localStorage.setItem(STYLE_KEY, result.style_id)
    }
    container.replaceChildren()
    if (!result.citation_groups.length) {
      const empty = document.createElement('p')
      empty.textContent = '当前文档还没有 Workmode 引文。'
      container.append(empty)
      return
    }
    for (const group of result.citation_groups) {
      const row = document.createElement('article')
      row.className = 'citation-group'
      const description = document.createElement('div')
      const text = document.createElement('p')
      text.textContent = group.text || 'Workmode 引文'
      const detail = document.createElement('small')
      detail.textContent = group.items
        .map((item) => String(item.metadata.title || item.paper_id))
        .join('；')
      description.append(text, detail)
      const actions = document.createElement('div')
      actions.className = 'citation-actions'
      const replace = document.createElement('button')
      replace.type = 'button'
      replace.textContent = '替换'
      replace.addEventListener('click', () => startReplacing(group))
      const remove = document.createElement('button')
      remove.type = 'button'
      remove.className = 'danger'
      remove.textContent = '移除'
      remove.addEventListener('click', () => void removeCitation(group))
      actions.append(replace, remove)
      row.append(description, actions)
      container.append(row)
    }
  } catch (error) {
    container.textContent = error instanceof Error ? error.message : '读取当前文档失败'
  }
}

async function bootstrap(): Promise<void> {
  if (mode === 'status') {
    element('workspace').hidden = true
    element('status-only').hidden = false
    element('status-message').textContent = params.get('message') || '操作完成。'
    element('title').textContent = 'Workmode'
    element('project-name').textContent = 'Word 引用'
    return
  }
  try {
    const result = await api<{
      project: { name: string }
      styles: Array<{ id: string; label: string }>
    }>('/word-addin/bootstrap')
    element('project-name').textContent = `当前文献库：${result.project.name}`
    element('title').textContent = mode === 'edit' ? '管理当前文档引文' : '搜索 Workmode 文献'
    const style = element<HTMLSelectElement>('style')
    for (const option of result.styles) {
      style.add(new Option(option.label, option.id))
    }
    style.value = localStorage.getItem(STYLE_KEY) || result.styles[0]?.id || ''
    await Promise.all([searchPapers(), loadInspection()])
  } catch (error) {
    setMessage(error instanceof Error ? error.message : '无法连接 Workmode', true)
  }
}

element('close').addEventListener('click', () => Office.context.ui.messageParent('close'))
element('search').addEventListener('input', () => {
  window.clearTimeout(searchTimer)
  searchTimer = window.setTimeout(() => void searchPapers(), 220)
})
element('insert').addEventListener('click', () => void submitCitation())
element('save-token').addEventListener('click', () => {
  const token = element<HTMLInputElement>('token').value.trim()
  if (token) localStorage.setItem(TOKEN_KEY, token)
  else localStorage.removeItem(TOKEN_KEY)
  void bootstrap()
})

Office.onReady(() => void bootstrap())
