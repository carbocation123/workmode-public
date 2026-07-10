import { describe, expect, it, vi } from 'vitest'
import { runDesktopUpdateFlow } from './desktopUpdateFlow'

describe('runDesktopUpdateFlow', () => {
  it('downloads before stopping the backend and installs only after the backend stopped', async () => {
    const calls: string[] = []
    const update = {
      download: vi.fn(async () => { calls.push('download') }),
      install: vi.fn(async () => { calls.push('install') })
    }
    const lifecycle = {
      prepare: vi.fn(async () => { calls.push('prepare') }),
      recover: vi.fn(async () => { calls.push('recover') }),
      relaunch: vi.fn(async () => { calls.push('relaunch') })
    }

    await runDesktopUpdateFlow(update, lifecycle)

    expect(calls).toEqual(['download', 'prepare', 'install', 'relaunch'])
    expect(lifecycle.recover).not.toHaveBeenCalled()
  })

  it('restarts the backend when installation fails after preparation', async () => {
    const failure = new Error('installer failed')
    const update = {
      download: vi.fn(async () => undefined),
      install: vi.fn(async () => { throw failure })
    }
    const lifecycle = {
      prepare: vi.fn(async () => undefined),
      recover: vi.fn(async () => undefined),
      relaunch: vi.fn(async () => undefined)
    }

    await expect(runDesktopUpdateFlow(update, lifecycle)).rejects.toBe(failure)

    expect(lifecycle.recover).toHaveBeenCalledOnce()
    expect(lifecycle.relaunch).not.toHaveBeenCalled()
  })
})
