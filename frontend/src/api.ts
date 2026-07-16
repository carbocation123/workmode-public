import { RUNTIME_API_BASE_KEY } from './literatureNavigation'

export interface Project {
  slug: string
  name: string
  root_path: string
  description: string
  created_at: string
  updated_at: string
  is_tutorial?: boolean
  parent_slug?: string | null
  archived_at?: string | null
  project_type?: string
  tool_profile?: string
  storage_mode?: 'managed' | 'external'
}

export interface Session {
  id: string
  title: string
  project_slug: string
  created_at: string
  updated_at: string
  message_count: number
  deleted_at?: string | null
}

export interface Message {
  id: string
  role: 'user' | 'assistant' | 'system' | 'tool'
  content: string
  ts: string
  meta: Record<string, unknown>
}

export interface FileEntry {
  path: string
  name: string
  kind: 'dir' | 'file'
  size: number
  preview: 'text' | 'media' | 'unsupported'
}

export interface FileContent {
  path: string
  content: string
  version: string
  size: number
  markdown: boolean
}

export interface ContextUsage {
  budget_tokens: number
  prompt_tokens_estimate: number
  project_prompt_file?: string | null
  project_prompt_tokens?: number
  project_prompt_total_tokens?: number
  estimated_prompt_tokens?: number
  history_tokens?: number
  total_tokens_estimate?: number
  history_message_count?: number
  history_messages_total?: number
  history_messages_included?: number
  history_messages_dropped?: number
  truncated?: boolean
  has_summary?: boolean
  imported_files: Array<{ path: string; char_count: number; token_count: number }>
  import_errors: string[]
  over_budget: boolean
  [key: string]: unknown
}

export interface AppSettings {
  data_dir: string
  host: string
  port: number
  model_base_url: string
  model_name: string
  model_api_key_set: boolean
  context_budget_tokens: number
  request_timeout_seconds: number
  mineru_api_key_set: boolean
  mineru_model_version: 'pipeline' | 'vlm'
  mineru_language: 'ch' | 'en' | 'ch_server' | 'japan'
  mineru_timeout_seconds: number
  dashscope_api_key_set: boolean
  transcription_workspace_dir: string
}

export interface ModelSettingsUpdate {
  model_base_url?: string
  model_name?: string
  model_api_key?: string
  clear_api_key?: boolean
  context_budget_tokens?: number
  request_timeout_seconds?: number
}

export interface ModelConnectionResult {
  ok: boolean
  message: string
  model: string
  latency_ms: number
}

export interface CompactionResult {
  session_id: string
  project_slug: string
  original_message_count: number
  kept_recent: number
  summarized_count: number
  summary_chars: number
  new_message_count: number
  compaction_seq: number
}

const DEFAULT_API_BASE = 'http://127.0.0.1:8765/api'
const cachedApiBase = typeof window !== 'undefined'
  ? window.sessionStorage.getItem(RUNTIME_API_BASE_KEY)
  : null
export let API_BASE = cachedApiBase || import.meta.env.VITE_WORKMODE_API_BASE || DEFAULT_API_BASE

export function setApiBase(value: string) {
  API_BASE = value.replace(/\/$/, '')
  if (typeof window !== 'undefined') window.sessionStorage.setItem(RUNTIME_API_BASE_KEY, API_BASE)
}

export interface MineruSettingsUpdate {
  mineru_api_key?: string
  clear_api_key?: boolean
  mineru_model_version?: 'pipeline' | 'vlm'
  mineru_language?: 'ch' | 'en' | 'ch_server' | 'japan'
  mineru_timeout_seconds?: number
}

export interface DashscopeSettingsUpdate {
  dashscope_api_key?: string
  clear_api_key?: boolean
}

export interface ActiveContextItem {
  kind: 'paper' | 'note'
  id: string
}

export interface ChatStreamEvent extends Record<string, unknown> {
  type: string
  content?: string
  context?: Partial<ContextUsage>
  message?: Message | string
  id?: string
  name?: string
  input?: Record<string, unknown>
  result?: string
  ok?: boolean
  changed_paths?: string[]
  round?: number
}

export function getToken(): string {
  return localStorage.getItem('workmode-public-token') || ''
}

export function setToken(token: string) {
  if (token.trim()) localStorage.setItem('workmode-public-token', token.trim())
  else localStorage.removeItem('workmode-public-token')
}

function headers(extra?: HeadersInit): HeadersInit {
  const token = getToken()
  return {
    'Content-Type': 'application/json',
    ...(token ? { 'X-Workmode-Token': token } : {}),
    ...(extra || {})
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: headers(init?.headers)
  })
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      detail = body.detail || detail
    } catch {
      // ignore non-json error body
    }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

export const api = {
  async settings() {
    return request<{ settings: AppSettings }>('/settings')
  },
  async saveModelSettings(payload: ModelSettingsUpdate) {
    return request<{ settings: AppSettings }>('/settings/model', {
      method: 'PUT',
      body: JSON.stringify(payload)
    })
  },
  async testModelConnection(payload: {
    model_base_url?: string
    model_name?: string
    model_api_key?: string
  }) {
    return request<ModelConnectionResult>('/settings/model/test', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  },
  async projects() {
    return request<{ projects: Project[]; active_slug: string | null }>('/work/projects')
  },
  async createProject(payload: { name: string; root_path: string; description: string }) {
    return request<{ project: Project; session: Session }>('/work/projects', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  },
  async saveMineruSettings(payload: MineruSettingsUpdate) {
    return request<{ settings: AppSettings }>('/settings/mineru', {
      method: 'PUT',
      body: JSON.stringify(payload)
    })
  },
  async saveDashscopeSettings(payload: DashscopeSettingsUpdate) {
    return request<{ settings: AppSettings }>('/settings/dashscope', {
      method: 'PUT',
      body: JSON.stringify(payload)
    })
  },
  async createLiteratureProject(payload: { name: string; root_path?: string }) {
    return request<{ project: Project; session: Session }>('/work/literature-projects', {
      method: 'POST',
      body: JSON.stringify(payload)
    })
  },
  async updateProject(slug: string, payload: { name?: string; description?: string }) {
    return request<{ project: Project }>(`/work/projects/${encodeURIComponent(slug)}`, {
      method: 'PATCH',
      body: JSON.stringify(payload)
    })
  },
  async installTutorialProject(parentPath: string) {
    return request<{ project: Project; session: Session }>('/work/tutorial-project', {
      method: 'POST',
      body: JSON.stringify({ parent_path: parentPath })
    })
  },
  async resetTutorialProject(slug: string) {
    return request<{ project: Project; session: Session; backup_path: string }>(
      `/work/projects/${encodeURIComponent(slug)}/reset-tutorial`,
      { method: 'POST' }
    )
  },
  async deleteProject(slug: string) {
    return request<{ project: Project; active_slug: string | null; local_files_deleted: boolean }>(
      `/work/projects/${encodeURIComponent(slug)}`,
      { method: 'DELETE' }
    )
  },
  async pickDirectory() {
    return request<{ path: string | null }>('/work/pick-directory', {
      method: 'POST'
    })
  },
  async setActive(slug: string) {
    return request<{ slug: string }>('/work/projects/active', {
      method: 'PUT',
      body: JSON.stringify({ slug })
    })
  },
  async sessions(slug: string) {
    return request<{ sessions: Session[] }>(`/work/projects/${encodeURIComponent(slug)}/sessions`)
  },
  async createSession(slug: string, title = '新对话') {
    return request<{ session: Session }>(`/work/projects/${encodeURIComponent(slug)}/sessions`, {
      method: 'POST',
      body: JSON.stringify({ title })
    })
  },
  async updateSession(sessionId: string, title: string) {
    return request<{ session: Session }>(`/work/sessions/${sessionId}`, {
      method: 'PATCH',
      body: JSON.stringify({ title })
    })
  },
  async deleteSession(sessionId: string) {
    return request<{ session: Session }>(`/work/sessions/${sessionId}`, {
      method: 'DELETE'
    })
  },
  async stopChat(sessionId: string) {
    return request<{ session_id: string; stopping: boolean }>(`/work/sessions/${sessionId}/stop`, {
      method: 'POST'
    })
  },
  async messages(sessionId: string) {
    return request<{ messages: Message[] }>(`/work/sessions/${sessionId}/messages?limit=60`)
  },
  async context(sessionId: string) {
    return request<{ context: ContextUsage }>(`/work/sessions/${sessionId}/context`)
  },
  async compact(sessionId: string, keepRecent = 6, extraInstruction = '') {
    return request<{ compaction: CompactionResult; context: ContextUsage }>(`/work/sessions/${sessionId}/compact`, {
      method: 'POST',
      body: JSON.stringify({ keep_recent: keepRecent, extra_instruction: extraInstruction })
    })
  },
  async tree(slug: string) {
    return request<{ entries: FileEntry[] }>(`/work/projects/${encodeURIComponent(slug)}/tree`)
  },
  async readFile(slug: string, path: string) {
    return request<FileContent>(`/work/projects/${encodeURIComponent(slug)}/fs/content?path=${encodeURIComponent(path)}`)
  },
  async saveFile(slug: string, path: string, content: string, version?: string) {
    return request<FileContent>(`/work/projects/${encodeURIComponent(slug)}/fs/content?path=${encodeURIComponent(path)}`, {
      method: 'PUT',
      body: JSON.stringify({ content, version })
    })
  },
  mediaUrl(slug: string, path: string) {
    const token = getToken()
    const url = new URL(`${API_BASE}/work/projects/${encodeURIComponent(slug)}/fs/media`, window.location.origin)
    url.searchParams.set('path', path)
    if (token) url.searchParams.set('token', token)
    return url.toString()
  },
  async memory(slug: string) {
    return request<{ global: string; project: string }>(`/work/projects/${encodeURIComponent(slug)}/memory`)
  },
  async saveMemory(slug: string, content: string) {
    return request<{ project: string }>(`/work/projects/${encodeURIComponent(slug)}/memory`, {
      method: 'PUT',
      body: JSON.stringify({ content })
    })
  }
}

export async function streamChat(
  sessionId: string,
  content: string,
  onEvent: (event: ChatStreamEvent) => void,
  signal?: AbortSignal,
  activeContext: ActiveContextItem[] = []
) {
  const response = await fetch(`${API_BASE}/work/sessions/${sessionId}/chat/stream`, {
    method: 'POST',
    headers: headers(),
    body: JSON.stringify({ content, ...(activeContext.length ? { active_context: activeContext } : {}) }),
    signal
  })
  if (!response.ok || !response.body) {
    throw new Error(`${response.status} ${response.statusText}`)
  }
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const blocks = buffer.split('\n\n')
    buffer = blocks.pop() || ''
    for (const block of blocks) {
      const data = block
        .split('\n')
        .find((line) => line.startsWith('data:'))
        ?.replace(/^data:\s*/, '')
      if (!data) continue
      onEvent(JSON.parse(data) as ChatStreamEvent)
    }
  }
}
