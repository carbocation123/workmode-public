import { invoke } from '@tauri-apps/api/core'
import { open } from '@tauri-apps/plugin-dialog'
import { openUrl } from '@tauri-apps/plugin-opener'
import { relaunch } from '@tauri-apps/plugin-process'
import { check, type DownloadEvent } from '@tauri-apps/plugin-updater'
import { runDesktopUpdateFlow } from './desktopUpdateFlow'

export interface DesktopInfo {
  apiBase: string
  version: string
  dataDir: string
  envFile: string
  migrationAvailable: boolean
}

export interface DesktopUpdateInfo {
  version: string
  date: string | null
  body: string | null
}

type CheckedUpdate = Awaited<ReturnType<typeof check>>

let desktopInfo: DesktopInfo | null = null
let pendingUpdate: Exclude<CheckedUpdate, null> | null = null

export function isDesktopApp() {
  return typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window
}

export async function initializeDesktop(): Promise<DesktopInfo | null> {
  if (!isDesktopApp()) return null
  desktopInfo = await invoke<DesktopInfo>('desktop_bootstrap')
  return desktopInfo
}

export function getDesktopInfo() {
  return desktopInfo
}

export async function openExternalUrl(url: string) {
  if (isDesktopApp()) {
    await openUrl(url)
    return
  }
  window.open(url, '_blank', 'noopener,noreferrer')
}

export async function checkForDesktopUpdate(): Promise<DesktopUpdateInfo | null> {
  if (!isDesktopApp()) return null
  pendingUpdate = await check()
  if (!pendingUpdate) return null
  return {
    version: pendingUpdate.version,
    date: pendingUpdate.date || null,
    body: pendingUpdate.body || null
  }
}

export async function installDesktopUpdate(
  onProgress: (downloaded: number, total: number | null) => void
) {
  if (!pendingUpdate) throw new Error('没有待安装的更新，请先检查更新')
  let downloaded = 0
  let total: number | null = null
  await runDesktopUpdateFlow(
    pendingUpdate,
    {
      prepare: () => invoke('desktop_prepare_update'),
      recover: () => invoke('desktop_recover_update'),
      relaunch
    },
    (event: DownloadEvent) => {
      if (event.event === 'Started') {
        total = event.data.contentLength ?? null
        onProgress(downloaded, total)
      } else if (event.event === 'Progress') {
        downloaded += event.data.chunkLength
        onProgress(downloaded, total)
      } else if (event.event === 'Finished') {
        onProgress(total ?? downloaded, total)
      }
    }
  )
}

export async function chooseAndMigrateLegacyPortable() {
  const selected = await open({
    directory: true,
    multiple: false,
    title: '选择旧版 Workmode Public 文件夹'
  })
  if (!selected || Array.isArray(selected)) return null
  const result = await invoke<{
    copiedData: boolean
    copiedConfig: boolean
    relaunchRequired: boolean
  }>('migrate_legacy', { legacyRoot: selected })
  if (result.relaunchRequired) await relaunch()
  return result
}
