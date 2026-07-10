export interface DownloadableUpdate<TEvent = unknown> {
  download(onEvent?: (event: TEvent) => void): Promise<void>
  install(): Promise<void>
}

export interface DesktopUpdateLifecycle {
  prepare(): Promise<void>
  recover(): Promise<void>
  relaunch(): Promise<void>
}

export async function runDesktopUpdateFlow<TEvent>(
  update: DownloadableUpdate<TEvent>,
  lifecycle: DesktopUpdateLifecycle,
  onEvent?: (event: TEvent) => void
) {
  await update.download(onEvent)
  await lifecycle.prepare()
  try {
    await update.install()
  } catch (error) {
    await lifecycle.recover()
    throw error
  }
  await lifecycle.relaunch()
}
