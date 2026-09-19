import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import type { Artifact, ChatMessage, SpaceDetail } from '../types'
import ArtifactTabs from '../components/ArtifactTabs'
import ChatPanel from '../components/ChatPanel'
import SourceList from '../components/SourceList'
import { Badge, Spinner } from '../components/ui'

export default function SpacePage() {
  const { spaceId = '' } = useParams()
  const [space, setSpace] = useState<SpaceDetail | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')

  const refresh = useCallback(async () => {
    const [s, m, a] = await Promise.all([
      api.getSpace(spaceId),
      api.listMessages(spaceId),
      api.listArtifacts(spaceId),
    ])
    setSpace(s)
    setMessages(m)
    setArtifacts(a)
    return s
  }, [spaceId])

  useEffect(() => {
    refresh().catch((e) => setError(e.message))
  }, [refresh])

  // Poll while the backend is generating materials.
  useEffect(() => {
    if (space?.status !== 'generating') return
    const t = setInterval(() => refresh().catch(() => {}), 2000)
    return () => clearInterval(t)
  }, [space?.status, refresh])

  const send = async (content: string) => {
    setSending(true)
    setError('')
    try {
      await api.sendChat(spaceId, content)
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Chat failed')
      await refresh().catch(() => {})
    } finally {
      setSending(false)
    }
  }

  if (!space) {
    return (
      <div className="flex h-screen items-center justify-center">
        {error ? <p className="text-red-600">{error}</p> : <Spinner label="Loading space..." />}
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col">
      <header className="flex items-center gap-4 border-b border-slate-200 bg-white px-6 py-3">
        <Link to="/" className="text-slate-400 hover:text-slate-600">
          ← Spaces
        </Link>
        <h1 className="text-lg font-semibold text-slate-900">{space.name}</h1>
        <Badge>{space.status}</Badge>
        {space.status === 'generating' && (
          <Spinner label="Generating your study materials..." />
        )}
      </header>

      {error && (
        <div className="border-b border-red-200 bg-red-50 px-6 py-2 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[280px_1fr_1.2fr]">
        <aside className="min-h-0 overflow-y-auto border-r border-slate-200 bg-slate-50">
          <SourceList
            spaceId={space.id}
            sources={space.sources}
            onChanged={refresh}
          />
        </aside>
        <main className="flex min-h-0 flex-col border-r border-slate-200">
          <ChatPanel
            messages={messages}
            onSend={send}
            sending={sending}
            generating={space.status === 'generating'}
          />
        </main>
        <aside className="min-h-0 overflow-y-auto bg-slate-50">
          <ArtifactTabs
            spaceId={space.id}
            spaceStatus={space.status}
            artifacts={artifacts}
            onChanged={refresh}
          />
        </aside>
      </div>
    </div>
  )
}
