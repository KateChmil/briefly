import type {
  Artifact,
  ArtifactKind,
  CalendarImportResult,
  CalendarItem,
  ChatMessage,
  ChatResponse,
  ImportResult,
  NewEvent,
  Source,
  SpaceDetail,
  SpaceSummary,
  StudySession,
  TeamsItem,
} from '../types'

// Empty in development (Vite proxies /api). Set VITE_API_URL to the backend's
// origin when the frontend is hosted separately, e.g. on Vercel.
const ORIGIN = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')
export const API_BASE = ORIGIN + '/api'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

function detailOf(body: unknown, fallback: string): string {
  const detail = (body as { detail?: unknown } | null)?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) {
    // FastAPI validation errors: [{ msg, loc }]
    return String((detail[0] as { msg?: string }).msg ?? fallback)
  }
  return fallback
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(API_BASE + path, init)
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Is the backend running?')
  }
  if (!res.ok) {
    let detail = res.statusText || `Request failed (${res.status})`
    try {
      detail = detailOf(await res.json(), detail)
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail)
  }
  return (res.status === 204 ? undefined : await res.json()) as T
}

function send<T>(method: string, path: string, body?: unknown): Promise<T> {
  return req<T>(path, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

const post = <T>(path: string, body?: unknown) => send<T>('POST', path, body)

function upload<T>(path: string, file: File): Promise<T> {
  const fd = new FormData()
  fd.append('file', file)
  return req<T>(path, { method: 'POST', body: fd })
}

export const api = {
  listSpaces: () => req<SpaceSummary[]>('/spaces'),
  createSpace: (name: string) => post<SpaceDetail>('/spaces', { name }),
  getSpace: (id: string) => req<SpaceDetail>(`/spaces/${id}`),
  deleteSpace: (id: string) => req<void>(`/spaces/${id}`, { method: 'DELETE' }),

  listMessages: (id: string) => req<ChatMessage[]>(`/spaces/${id}/messages`),
  sendChat: (id: string, content: string) =>
    post<ChatResponse>(`/spaces/${id}/chat`, { content }),

  uploadSource: (id: string, file: File) =>
    upload<Source>(`/spaces/${id}/sources`, file),
  deleteSource: (id: string, sourceId: string) =>
    req<void>(`/spaces/${id}/sources/${sourceId}`, { method: 'DELETE' }),

  listTeams: () => req<TeamsItem[]>('/teams'),
  listChannels: (teamId: string) =>
    req<TeamsItem[]>(`/teams/channels?team_id=${encodeURIComponent(teamId)}`),
  listTeamsFiles: (channelId: string) =>
    req<TeamsItem[]>(`/teams/files?channel_id=${encodeURIComponent(channelId)}`),
  importTeamsFiles: (id: string, fileIds: string[]) =>
    post<ImportResult>(`/spaces/${id}/sources/teams`, { file_ids: fileIds }),

  listArtifacts: (id: string) => req<Artifact[]>(`/spaces/${id}/artifacts`),
  regenerateArtifact: (id: string, kind: ArtifactKind) =>
    post<Artifact>(`/spaces/${id}/artifacts/${kind}/regenerate`),
  generateAll: (id: string) => post<SpaceDetail>(`/spaces/${id}/generate`),

  listSessions: (id: string) => req<StudySession[]>(`/spaces/${id}/sessions`),
  setSessionDone: (sessionId: number, done: boolean) =>
    send<StudySession>('PATCH', `/sessions/${sessionId}`, { done }),

  getCalendar: (start: string, end: string, spaceId?: string) =>
    req<CalendarItem[]>(
      `/calendar?start=${start}&end=${end}` +
        (spaceId ? `&space_id=${encodeURIComponent(spaceId)}` : ''),
    ),
  createEvent: (event: NewEvent) => post<CalendarItem>('/calendar/events', event),
  deleteEvent: (eventId: string) =>
    req<void>(`/calendar/events/${eventId.replace('event-', '')}`, {
      method: 'DELETE',
    }),
  importCalendarFile: (file: File, spaceId?: string) =>
    upload<CalendarImportResult>(
      `/calendar/import${spaceId ? `?space_id=${encodeURIComponent(spaceId)}` : ''}`,
      file,
    ),
  importCalendarUrl: (url: string, spaceId?: string) =>
    post<CalendarImportResult>('/calendar/import-url', {
      url,
      space_id: spaceId || null,
    }),
  exportUrl: (spaceId?: string) =>
    `${API_BASE}/calendar/export.ics${spaceId ? `?space_id=${encodeURIComponent(spaceId)}` : ''}`,
}
