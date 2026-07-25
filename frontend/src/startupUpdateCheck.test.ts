import { describe, expect, it, vi } from 'vitest'

import { createStartupUpdateCheck } from './startupUpdateCheck'

describe('createStartupUpdateCheck', () => {
  it('reuses one update request throughout the current app launch', async () => {
    const check = vi.fn(async () => ({ version: '0.8.12' }))
    const run = createStartupUpdateCheck(check)

    const first = run()
    const second = run()

    expect(first).toBe(second)
    await expect(first).resolves.toEqual({ version: '0.8.12' })
    expect(check).toHaveBeenCalledOnce()
  })

  it('keeps update failures non-blocking and does not retry during the same launch', async () => {
    const failure = new Error('offline')
    const check = vi.fn(async () => {
      throw failure
    })
    const onError = vi.fn()
    const run = createStartupUpdateCheck(check, onError)

    await expect(run()).resolves.toBeNull()
    await expect(run()).resolves.toBeNull()
    expect(check).toHaveBeenCalledOnce()
    expect(onError).toHaveBeenCalledWith(failure)
  })
})
