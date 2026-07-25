import { invoke } from '@tauri-apps/api/core'
import { open } from '@tauri-apps/plugin-dialog'
import { openPath, openUrl, revealItemInDir } from '@tauri-apps/plugin-opener'
import { relaunch } from '@tauri-apps/plugin-process'
import { check, type DownloadEvent } from '@tauri-apps/plugin-updater'
import { runDesktopUpdateFlow } from './desktopUpdateFlow'
import { createStartupUpdateCheck } from './startupUpdateCheck'

export interface DesktopInfo {
  apiBase: string
  version: string
  dataDir: string
  envFile: string
  runId: string
  migrationAvailable: boolean
}

export interface DesktopBugReport {
  path: string
  fileName: string
  runId: string
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

export async function logDesktopFrontendEvent(level: string, category: string, message: string) {
  if (!isDesktopApp()) return
  await invoke('desktop_log_event', { level, category, message })
}

export async function generateDesktopBugReport(report: string): Promise<DesktopBugReport | null> {
  if (!isDesktopApp()) return null
  const bundle = await invoke<DesktopBugReport>('desktop_generate_bug_report', { report })
  await revealItemInDir(bundle.path)
  return bundle
}

export async function revealLocalItem(path: string): Promise<boolean> {
  if (!isDesktopApp()) return false
  await revealItemInDir(path)
  return true
}

export async function openLocalPath(path: string): Promise<boolean> {
  if (!isDesktopApp()) return false
  await openPath(path)
  return true
}

export async function chooseEndNoteLibrary(): Promise<string | null> {
  if (!isDesktopApp()) return null
  const selected = await open({
    directory: false,
    multiple: false,
    title: '选择 EndNote 文献库',
    filters: [{ name: 'EndNote 文献库', extensions: ['enl', 'enlx'] }],
  })
  return typeof selected === 'string' ? selected : null
}

export async function chooseZoteroLibrary(): Promise<string | null> {
  if (!isDesktopApp()) return null
  const selected = await open({
    directory: false,
    multiple: false,
    title: '选择 Zotero 数据库',
    filters: [{ name: 'Zotero 数据库', extensions: ['sqlite'] }],
  })
  return typeof selected === 'string' ? selected : null
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

const runStartupDesktopUpdateCheck = createStartupUpdateCheck(
  checkForDesktopUpdate,
  (error) => {
    const message = error instanceof Error ? `${error.name}: ${error.message}` : String(error)
    void logDesktopFrontendEvent('warning', 'desktop_update_startup_check', message).catch(() => undefined)
  },
)

export function checkForDesktopUpdateOnStartup(): Promise<DesktopUpdateInfo | null> {
  if (!isDesktopApp()) return Promise.resolve(null)
  return runStartupDesktopUpdateCheck()
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
