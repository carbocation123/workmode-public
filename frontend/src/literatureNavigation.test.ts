import { describe, expect, it } from 'vitest'

import {
  applicationHomeUrl,
  literatureWorkbenchUrl,
  transcriptionWorkbenchUrl,
  writingWorkbenchUrl,
  resolveApplicationSurface,
  resolveSettingsReturnSurface,
  resolveWorkbenchPanel,
  workbenchSettingsUrl,
  workbenchUrl,
} from './literatureNavigation'

describe('literature workbench navigation', () => {
  it('opens the packaged nested page from the main workbench', () => {
    expect(literatureWorkbenchUrl('http://tauri.localhost/')).toBe('http://tauri.localhost/literature/index.html')
    expect(literatureWorkbenchUrl('http://127.0.0.1:5173/index.html')).toBe('http://127.0.0.1:5173/literature/index.html')
  })

  it('keeps the application home separate from the heavy workbench', () => {
    expect(applicationHomeUrl('http://tauri.localhost/literature/')).toBe('http://tauri.localhost/index.html')
    expect(workbenchUrl('http://tauri.localhost/index.html')).toBe('http://tauri.localhost/index.html?surface=workbench')
  })

  it('opens meeting transcription as a sessionless sibling surface', () => {
    expect(transcriptionWorkbenchUrl('http://tauri.localhost/')).toBe('http://tauri.localhost/transcription/index.html')
    expect(transcriptionWorkbenchUrl('http://127.0.0.1:5173/index.html')).toBe('http://127.0.0.1:5173/transcription/index.html')
  })

  it('opens article processing as a sessionless sibling surface', () => {
    expect(writingWorkbenchUrl('http://tauri.localhost/')).toBe('http://tauri.localhost/writing/index.html')
    expect(writingWorkbenchUrl('http://127.0.0.1:5173/index.html')).toBe('http://127.0.0.1:5173/writing/index.html')
  })

  it('opens on the application home and restores the explicit workbench surface', () => {
    expect(resolveApplicationSurface('http://tauri.localhost/index.html')).toBe('home')
    expect(resolveApplicationSurface('http://tauri.localhost/index.html?surface=workbench')).toBe('workbench')
  })

  it('opens the shared settings page and can return to literature', () => {
    const url = workbenchSettingsUrl('http://tauri.localhost/literature/index.html', 'literature')
    expect(url).toBe('http://tauri.localhost/index.html?surface=workbench&panel=settings&return=literature')
    expect(resolveWorkbenchPanel(url)).toBe('settings')
    expect(resolveSettingsReturnSurface(url)).toBe('literature')
    expect(resolveWorkbenchPanel(workbenchUrl(url))).toBe('project')
  })
})
