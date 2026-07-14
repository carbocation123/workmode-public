import { describe, expect, it } from 'vitest'

import { createUnavailableRuntime, EMPTY_RUNTIME_SESSION } from './runtimeState'

describe('literature runtime state', () => {
  it('never falls back to sample papers, messages, notes, or memory when the backend is unavailable', () => {
    const runtime = createUnavailableRuntime('后端连接失败')

    expect(runtime.papers).toEqual([])
    expect(runtime.notes).toEqual([])
    expect(runtime.tags).toEqual([])
    expect(runtime.projectMemory).toEqual([])
    expect(runtime.session).toEqual(EMPTY_RUNTIME_SESSION)
    expect(runtime.session.messages).toEqual([])
    expect(runtime.canMutate).toBe(false)
    expect(runtime.error).toBe('后端连接失败')
  })
})
