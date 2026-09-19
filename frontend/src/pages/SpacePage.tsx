import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../api/client'
import ArtifactTabs from '../components/ArtifactTabs'
import ChatPanel from '../components/ChatPanel'
import SourceList from '../components/SourceList'
import { Badge, Countdown, ErrorNote, ProgressBar, Spinner } from '../components/ui'
import { useSpaces } from '../lib/spaces'
import { spaceColor } from '../lib/theme'
import type { Artifact, ChatMessage, SpaceDetail, SpaceStatus, StudySession } from '../types'

const STATUS: Record<SpaceStatus, { label: string; tone: string }> = {
  interviewing: { label: 'Setting up', tone: 'bg-amber-50 text-amber-700 ring-amber-200' },
  generating: { label: 'Generating…', tone: 'bg-indigo-50 text-indigo-700 ring-indigo-200' },
  ready: { label: 'Ready', tone: 'bg-emerald-50 text-emerald-700 ring-emerald-200' },
}

type Panel = 'chat' | 'materials' | 'sources'
const PANELS: { id: Panel; label: string }[] = [
  { id: 'chat', label: '💬 Chat' },
  { id: 'materials', label: '📚 Study' },
  { id: 'sources', label: '📎 Sources' },
]

export default function SpacePage() {
  const { spaceId = '' } = useParams()
  const { reload: reloadSpaces } = useSpaces()
  const [space, setSpace] = useState<SpaceDetail | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [artifacts, setArtifacts] = useState<Artifact[]>([])
  const [sessions, setSessions] = useState<StudySession[]>([])
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const [panel, setPanel] = useState<Panel>('chat') // small screens only

  const refresh = useCallback(async () => {
    const [s, m, a, ss] = await Promise.all([
      api.getSpace(spaceId),
      api.listMessages(spaceId),
      api.listArtifacts(spaceId),
      api.listSessions(spaceId),
    ])
    setSpace(s)
    setMessages(m)
    setArtifacts(a)
    setSessions(ss)
    return s
  }, [spaceId])

  useEffect(() => {
    setSpace(null)
    setError('')
    refresh().catch((e) => setError(e.message))
  }, [refresh])

  // While the backend builds materials in the background, poll so each piece
  // shows up as soon as it is ready.
  const generating = space?.status === 'generating'
  useEffect(() => {
    if (!generating) return
    const t = setInterval(() => {
      refresh()
        .then((s) => s.status !== 'generating' && void reloadSpaces())
        .catch(() => {})
    }, 2000)
    return () => clearInterval(t)
  }, [generating, refresh, reloadSpaces])

  const send = async (content: string): Promise<boolean> => {
    setSending(true)
    setError('')
    // show the message straight away instead of after the round trip
    setMessages((prev) => [
      ...prev,
      { id: -Date.now(), role: 'user', content, created_at: new Date().toISOString() },
    ])
    try {
      const res = await api.sendChat(spaceId, content)
      await refresh()
      if (res.profile_completed || res.plan_updating) setPanel('materials')
      return true
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Chat failed')
      await refresh().catch(() => {})
      return false
    } finally {
      setSending(false)
    }
  }

  const generateAll = async () => {
    setError('')
    try {
      await api.generateAll(spaceId)
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not start generation')
    }
  }

  const toggleSession = async (session: StudySession, done: boolean) => {
    setSessions((prev) => prev.map((s) => (s.id === session.id ? { ...s, done } : s)))
    try {
      await api.setSessionDone(session.id, done)
      void reloadSpaces()
    } catch (e) {
      setSessions((prev) => prev.map((s) => (s.id === session.id ? { ...s, done: !done } : s)))
      setError(e instanceof Error ? e.message : 'Could not update the session')
    }
  }

  if (!space) {
    return (
      <div className="flex h-full items-center justify-center p-8">
        {error ? (
          <div className="max-w-sm space-y-3 text-center">
            <ErrorNote>{error}</ErrorNote>
            <Link to="/" className="text-sm font-medium text-indigo-600 hover:underline">
              ← Back to dashboard
            </Link>
          </div>
        ) : (
          <Spinner label="Loading subject…" />
        )}
      </div>
    )
  }

  const color = spaceColor(space.id)
  const status = STATUS[space.status]
  const done = sessions.filter((s) => s.done).length

  return (
    <div className="flex h-full min-h-0 flex-col">
      <header className="border-b border-slate-200 bg-white px-4 py-3 sm:px-6">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <span className={`h-3 w-3 rounded-full ${color.dot}`} />
          <h1 className="text-lg font-bold tracking-tight text-slate-900">{space.name}</h1>
          <Badge className={status.tone}>{status.label}</Badge>
          {space.exam_date && <Countdown date={space.exam_date} />}
          {sessions.length > 0 && (
            <div className="ml-auto flex w-full items-center gap-2 sm:w-56">
              <ProgressBar value={done} max={sessions.length} gradient={color.bar} className="flex-1" />
              <span className="shrink-0 text-xs text-slate-500">
                {done}/{sessions.length}
              </span>
            </div>
          )}
        </div>
      </header>

      {error && (
        <div className="border-b border-rose-200 bg-rose-50 px-4 py-2 text-sm text-rose-700 sm:px-6">
          {error}
        </div>
      )}

      {/* phone / tablet: switch between the three panes */}
      <nav className="flex gap-1 border-b border-slate-200 bg-white px-3 py-1.5 lg:hidden">
        {PANELS.map((p) => (
          <button
            key={p.id}
            onClick={() => setPanel(p.id)}
            className={`flex-1 rounded-xl px-3 py-1.5 text-sm font-medium transition ${
              panel === p.id ? 'bg-indigo-100 text-indigo-700' : 'text-slate-500 hover:bg-slate-100'
            }`}
          >
            {p.label}
          </button>
        ))}
      </nav>

      <div className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[17rem_minmax(0,1fr)_minmax(0,1.25fr)]">
        <aside
          className={`min-h-0 overflow-y-auto border-r border-slate-200 bg-slate-50 ${
            panel === 'sources' ? 'block' : 'hidden'
          } lg:block`}
        >
          <SourceList spaceId={space.id} sources={space.sources} onChanged={refresh} />
        </aside>

        <main
          className={`min-h-0 flex-col border-r border-slate-200 bg-slate-50/60 ${
            panel === 'chat' ? 'flex' : 'hidden'
          } lg:flex`}
        >
          <ChatPanel messages={messages} status={space.status} onSend={send} sending={sending} />
        </main>

        <aside
          className={`min-h-0 overflow-y-auto bg-slate-50 ${
            panel === 'materials' ? 'block' : 'hidden'
          } lg:block`}
        >
          <ArtifactTabs
            spaceId={space.id}
            spaceName={space.name}
            spaceStatus={space.status}
            hasProfile={!!space.profile}
            artifacts={artifacts}
            sessions={sessions}
            onToggleSession={toggleSession}
            onChanged={refresh}
            onGenerate={generateAll}
          />
        </aside>
      </div>
    </div>
  )
}
