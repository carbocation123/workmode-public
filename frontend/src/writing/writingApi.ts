import { API_BASE, getToken } from '../api'
import type { DeletedWritingHistory, WritingHistoryRecord, WritingHistorySummary, WritingMode } from './model'


export interface WritingStatus {
  model_api_configured: boolean
  model_name: string
  history_path: string
}


function authHeaders(extra?: HeadersInit): HeadersInit {
  const token = getToken()
  return {
    ...(token ? { 'X-Workmode-Token': token } : {}),
    ...(extra || {}),
  }
}


async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}/writing${path}`, {
    ...init,
    headers: authHeaders(init?.headers),
  })
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      detail = body.detail || detail
    } catch {
      // Preserve the HTTP fallback for non-JSON failures.
    }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}


export async function getWritingStatus(): Promise<WritingStatus> {
  return request<WritingStatus>('/status')
}


export async function processText(mode: WritingMode, inputText: string): Promise<WritingHistoryRecord> {
  const result = await request<{ record: WritingHistoryRecord }>('/process', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode, input_text: inputText }),
  })
  return result.record
}


export async function listHistory(): Promise<WritingHistorySummary[]> {
  return (await request<{ items: WritingHistorySummary[] }>('/history')).items
}


export async function loadHistoryRecord(recordId: string): Promise<WritingHistoryRecord> {
  return (await request<{ record: WritingHistoryRecord }>(`/history/${encodeURIComponent(recordId)}`)).record
}


export async function deleteHistory(recordId: string): Promise<DeletedWritingHistory> {
  return (await request<{ trash: DeletedWritingHistory }>(`/history/${encodeURIComponent(recordId)}`, {
    method: 'DELETE',
  })).trash
}


export async function listTrash(): Promise<DeletedWritingHistory[]> {
  return (await request<{ items: DeletedWritingHistory[] }>('/trash')).items
}


export async function restoreHistory(trashId: string): Promise<WritingHistoryRecord> {
  return (await request<{ record: WritingHistoryRecord }>(`/trash/${encodeURIComponent(trashId)}/restore`, {
    method: 'POST',
  })).record
}
