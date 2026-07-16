import { API_BASE, getToken } from '../api'
import type { TranscriptSegment, TranscriptionJob } from './model'

export interface TranscriptionWorkspaceInfo {
  path: string
  dashscope_api_key_set: boolean
  model: string
  supported_extensions: string[]
}

export interface TranscriptResult {
  job: TranscriptionJob
  segments: TranscriptSegment[]
  markdown: string
  text: string
}

export interface DeletedTranscription {
  trash_id: string
  job_id: string
  deleted_at: string
  job: TranscriptionJob
}

function authHeaders(extra?: HeadersInit): HeadersInit {
  const token = getToken()
  return {
    ...(token ? { 'X-Workmode-Token': token } : {}),
    ...(extra || {}),
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}/transcription${path}`, {
    ...init,
    headers: authHeaders(init?.headers),
  })
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`
    try {
      const body = await response.json()
      detail = body.detail || detail
    } catch {
      // Keep the HTTP fallback for non-JSON failures.
    }
    throw new Error(detail)
  }
  return response.json() as Promise<T>
}

export async function getWorkspaceInfo(): Promise<TranscriptionWorkspaceInfo> {
  return request<TranscriptionWorkspaceInfo>('/workspace')
}

export async function listJobs(): Promise<TranscriptionJob[]> {
  return (await request<{ jobs: TranscriptionJob[] }>('/jobs')).jobs
}

export async function uploadAudio(file: File): Promise<TranscriptionJob> {
  const result = await request<{ job: TranscriptionJob }>(
    `/jobs?filename=${encodeURIComponent(file.name)}`,
    {
      method: 'POST',
      headers: { 'Content-Type': file.type || 'application/octet-stream' },
      body: file,
    },
  )
  return result.job
}

export async function readTranscript(jobId: string): Promise<TranscriptResult> {
  return request<TranscriptResult>(`/jobs/${encodeURIComponent(jobId)}/transcript`)
}

export async function renameJob(jobId: string, title: string): Promise<TranscriptionJob> {
  return (await request<{ job: TranscriptionJob }>(`/jobs/${encodeURIComponent(jobId)}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title }),
  })).job
}

export async function retryJob(jobId: string): Promise<TranscriptionJob> {
  return (await request<{ job: TranscriptionJob }>(`/jobs/${encodeURIComponent(jobId)}/retry`, {
    method: 'POST',
  })).job
}

export async function deleteJob(jobId: string): Promise<DeletedTranscription> {
  return (await request<{ trash: DeletedTranscription }>(`/jobs/${encodeURIComponent(jobId)}`, {
    method: 'DELETE',
  })).trash
}

export async function listTrash(): Promise<DeletedTranscription[]> {
  return (await request<{ items: DeletedTranscription[] }>('/trash')).items
}

export async function restoreJob(trashId: string): Promise<TranscriptionJob> {
  return (await request<{ job: TranscriptionJob }>(`/trash/${encodeURIComponent(trashId)}/restore`, {
    method: 'POST',
  })).job
}

export function transcriptFileUrl(jobId: string, kind: 'text' | 'markdown' | 'json'): string {
  const url = new URL(`${API_BASE}/transcription/jobs/${encodeURIComponent(jobId)}/files/${kind}`)
  const token = getToken()
  if (token) url.searchParams.set('token', token)
  return url.toString()
}
