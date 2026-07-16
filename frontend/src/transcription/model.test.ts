import { describe, expect, it } from 'vitest'

import { nextSelectedJobId, sortJobs, statusLabel, type TranscriptionJob } from './model'

function job(id: string, updatedAt: string, status: TranscriptionJob['status'] = 'completed'): TranscriptionJob {
  return {
    id,
    title: id,
    original_name: `${id}.m4a`,
    status,
    model: 'fun-asr',
    input_path: `input/${id}/recording.m4a`,
    output_path: `output/${id}`,
    created_at: updatedAt,
    updated_at: updatedAt,
    remote_task_id: null,
    error: null,
  }
}

describe('transcription list model', () => {
  it('sorts multiple files by most recent update without mutating the API list', () => {
    const original = [job('old', '2026-07-16T00:00:00Z'), job('new', '2026-07-17T00:00:00Z')]

    expect(sortJobs(original).map((item) => item.id)).toEqual(['new', 'old'])
    expect(original.map((item) => item.id)).toEqual(['old', 'new'])
  })

  it('keeps the current file selected after returning to the module', () => {
    const jobs = [job('new', '2026-07-17T00:00:00Z'), job('old', '2026-07-16T00:00:00Z')]

    expect(nextSelectedJobId('old', jobs)).toBe('old')
    expect(nextSelectedJobId('missing', jobs)).toBe('new')
    expect(nextSelectedJobId(null, [])).toBeNull()
  })

  it('uses user-facing labels for every persistent task status', () => {
    expect(statusLabel('queued')).toBe('等待转写')
    expect(statusLabel('transcribing')).toBe('正在转写')
    expect(statusLabel('completed')).toBe('转写完成')
    expect(statusLabel('failed')).toBe('转写失败')
  })
})
