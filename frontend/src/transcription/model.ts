export type TranscriptionStatus = 'queued' | 'transcribing' | 'completed' | 'failed'

export interface TranscriptionJob {
  id: string
  title: string
  original_name: string
  status: TranscriptionStatus
  model: 'fun-asr' | string
  input_path: string
  output_path: string
  remote_task_id: string | null
  duration_ms?: number | null
  error: string | null
  created_at: string
  updated_at: string
  workspace_path?: string
  output_directory?: string
  reveal_path?: string
}

export interface TranscriptSegment {
  seq: number
  raw_speaker_id: number | string
  speaker: string
  start_ms: number
  end_ms: number
  text: string
  is_overlap: boolean
}

export function sortJobs(jobs: TranscriptionJob[]): TranscriptionJob[] {
  return [...jobs].sort((left, right) => right.updated_at.localeCompare(left.updated_at))
}

export function nextSelectedJobId(currentId: string | null, jobs: TranscriptionJob[]): string | null {
  if (currentId && jobs.some((job) => job.id === currentId)) return currentId
  return jobs[0]?.id || null
}

export function statusLabel(status: TranscriptionStatus): string {
  return {
    queued: '等待转写',
    transcribing: '正在转写',
    completed: '转写完成',
    failed: '转写失败',
  }[status]
}

export function formatDuration(milliseconds?: number | null): string {
  if (!milliseconds) return '时长待识别'
  const seconds = Math.floor(milliseconds / 1000)
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const rest = seconds % 60
  return hours
    ? `${hours}:${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`
    : `${minutes}:${String(rest).padStart(2, '0')}`
}

export function formatTimestamp(milliseconds: number): string {
  const seconds = Math.max(0, Math.floor(milliseconds / 1000))
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  const rest = seconds % 60
  return hours
    ? `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`
    : `${String(minutes).padStart(2, '0')}:${String(rest).padStart(2, '0')}`
}
