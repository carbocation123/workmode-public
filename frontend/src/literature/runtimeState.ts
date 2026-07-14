export interface EmptyRuntimeSession {
  id: string
  name: string
  messages: []
  attachedPaperIds: []
  attachedNoteIds: []
  contextPercent: number
}

export const EMPTY_RUNTIME_SESSION: EmptyRuntimeSession = {
  id: 'backend-unavailable',
  name: '后端未连接',
  messages: [],
  attachedPaperIds: [],
  attachedNoteIds: [],
  contextPercent: 0,
}

export function createUnavailableRuntime(error: string) {
  return {
    papers: [],
    notes: [],
    tags: [],
    projectMemory: [],
    session: EMPTY_RUNTIME_SESSION,
    canMutate: false,
    error,
  }
}
