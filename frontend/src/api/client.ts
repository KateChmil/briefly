import type {
  Artifact,
  ArtifactKind,
  ChatMessage,
  ChatResponse,
  ImportResult,
  Source,
  SpaceDetail,
  SpaceSummary,
  TeamsItem,
} from '../types'

const BASE = '/api'

export class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function req<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(BASE + path, init)
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      if (body?.detail) detail = String(body.detail)
    } catch {
      /* keep statusText */
    }
    throw new ApiError(res.status, detail)
  }
  return (res.status === 204 ? undefined : await res.json()) as T
}

function post<T>(path: string, body: unknown): Promise<T> {
  return req<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

export const api = {
  listSpaces: () => req<SpaceSummary[]>('/spaces'),
  createSpace: (name: string) => post<SpaceDetail>('/spaces', { name }),
  getSpace: (id: string) => req<SpaceDetail>(`/spaces/${id}`),
  deleteSpace: (id: string) => req<void>(`/spaces/${id}`, { method: 'DELETE' }),

  listMessages: (id: string) => req<ChatMessage[]>(`/spaces/${id}/messages`),
  sendChat: (id: string, content: string) =>
    post<ChatResponse>(`/spaces/${id}/chat`, { content }),

  uploadSource: (id: string, file: File) => {
    const fd = new FormData()
    fd.append('file', file)
    return req<Source>(`/spaces/${id}/sources`, { method: 'POST', body: fd })
  },
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
    req<Artifact>(`/spaces/${id}/artifacts/${kind}/regenerate`, {
      method: 'POST',
    }),
}
