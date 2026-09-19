import { useCallback, useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { api } from '../api/client'
import type { NoteAction, NoteEnhanceResult, UserNote } from '../types'
import { Button, ErrorNote, Spinner, inputClass } from './ui'

const ACTIONS: { id: NoteAction; label: string; icon: string }[] = [
  { id: 'summarize', label: 'Summarise', icon: '✂️' },
  { id: 'key_terms', label: 'Key terms', icon: '🔑' },
  { id: 'simplify', label: 'Simplify', icon: '🧸' },
  { id: 'improve', label: 'Improve', icon: '✨' },
  { id: 'quiz_me', label: 'Quiz me', icon: '❓' },
  { id: 'flashcards', label: 'Flashcards', icon: '🃏' },
]

const SAVE_DELAY = 1000

type SaveState = 'idle' | 'saving' | 'saved' | 'error'

export default function MyNotes({ spaceId }: { spaceId: string }) {
  const [notes, setNotes] = useState<UserNote[] | null>(null)
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [saveState, setSaveState] = useState<SaveState>('idle')
  const [preview, setPreview] = useState(false)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState<NoteAction | null>(null)
  const [enhanced, setEnhanced] = useState<NoteEnhanceResult | null>(null)
  const [copied, setCopied] = useState(false)

  // The debounced save reads these refs, so it always sends the latest draft.
  const draft = useRef({ id: 0, title: '', content: '' })
  const dirty = useRef(false)
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null)

  const saveNow = useCallback(async () => {
    if (!dirty.current) return
    const { id, title: t, content: c } = draft.current
    dirty.current = false
    setSaveState('saving')
    try {
      const updated = await api.updateUserNote(id, { title: t, content: c })
      setNotes((prev) => prev?.map((n) => (n.id === id ? updated : n)) ?? null)
      setSaveState(dirty.current ? 'saving' : 'saved')
      if (dirty.current) {
        timer.current = setTimeout(() => void saveNow(), SAVE_DELAY)
      }
    } catch {
      setSaveState('error')
    }
  }, [])

  const flushSave = useCallback(async () => {
    if (timer.current) clearTimeout(timer.current)
    timer.current = null
    await saveNow()
  }, [saveNow])

  const scheduleSave = useCallback(
    (id: number, t: string, c: string) => {
      draft.current = { id, title: t, content: c }
      dirty.current = true
      setSaveState('saving')
      if (timer.current) clearTimeout(timer.current)
      timer.current = setTimeout(() => void saveNow(), SAVE_DELAY)
    },
    [saveNow],
  )

  const select = useCallback(
    (n: UserNote | null) => {
      void flushSave() // don't lose pending edits when switching notes
      setSelectedId(n?.id ?? null)
      setTitle(n?.title ?? '')
      setContent(n?.content ?? '')
      setSaveState('idle')
      setPreview(false)
      setEnhanced(null)
      setError('')
    },
    [flushSave],
  )

  useEffect(() => {
    let cancelled = false
    setNotes(null)
    setSelectedId(null)
    api
      .listUserNotes(spaceId)
      .then((list) => {
        if (cancelled) return
        setNotes(list)
        if (list.length) select(list[0])
      })
      .catch(
        (e) =>
          !cancelled &&
          setError(e instanceof Error ? e.message : 'Could not load notes'),
      )
    return () => {
      cancelled = true
    }
  }, [spaceId, select])

  // Last-chance save when the component unmounts mid-edit.
  useEffect(() => {
    return () => {
      if (timer.current) clearTimeout(timer.current)
      if (dirty.current) {
        const { id, title: t, content: c } = draft.current
        void api.updateUserNote(id, { title: t, content: c }).catch(() => {})
      }
    }
  }, [])

  const create = async () => {
    setError('')
    try {
      const note = await api.createUserNote(spaceId, {
        title: 'Untitled note',
        content: '',
      })
      setNotes((prev) => [note, ...(prev ?? [])])
      select(note)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not create the note')
    }
  }

  const remove = async (n: UserNote) => {
    setError('')
    try {
      await api.deleteUserNote(n.id)
      setNotes((prev) => prev?.filter((x) => x.id !== n.id) ?? null)
      if (selectedId === n.id) select(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not delete the note')
    }
  }

  const onTitle = (v: string) => {
    setTitle(v)
    if (selectedId != null) scheduleSave(selectedId, v, content)
  }

  const onContent = (v: string) => {
    setContent(v)
    if (selectedId != null) scheduleSave(selectedId, title, v)
  }

  const enhance = async (action: NoteAction) => {
    if (selectedId == null || busy) return
    setError('')
    setEnhanced(null)
    setCopied(false)
    await flushSave() // make sure the server has the latest text first
    setBusy(action)
    try {
      setEnhanced(await api.enhanceNote(selectedId, action))
    } catch (e) {
      setError(
        e instanceof Error
          ? e.message
          : 'The AI could not help right now. Try again in a moment.',
      )
    } finally {
      setBusy(null)
    }
  }

  const append = () => {
    if (!enhanced || selectedId == null) return
    const next = content.trimEnd()
      ? `${content.trimEnd()}\n\n${enhanced.result}`
      : enhanced.result
    onContent(next)
    setEnhanced(null)
  }

  const copy = async () => {
    if (!enhanced) return
    try {
      await navigator.clipboard.writeText(enhanced.result)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      setError('Could not copy to the clipboard')
    }
  }

  const selected = notes?.find((n) => n.id === selectedId) ?? null

  if (notes === null) {
    return (
      <div className="p-4">
        <Spinner label="Loading your notes…" />
      </div>
    )
  }

  return (
    <div className="flex flex-col gap-3">
      {error && <ErrorNote>{error}</ErrorNote>}

      {/* note list + new note */}
      <div className="flex items-center gap-2 overflow-x-auto pb-1">
        <Button size="sm" onClick={() => void create()} className="shrink-0">
          + New note
        </Button>
        {notes.map((n) => (
          <button
            key={n.id}
            onClick={() => select(n)}
            className={`shrink-0 rounded-xl px-3 py-1.5 text-xs font-medium transition ${
              n.id === selectedId
                ? 'bg-indigo-100 text-indigo-700'
                : 'bg-white text-slate-600 ring-1 ring-slate-200 hover:bg-slate-50'
            }`}
          >
            {n.title || 'Untitled note'}
          </button>
        ))}
        {notes.length === 0 && (
          <span className="text-xs text-slate-400">
            No notes yet — write your own and let the AI tidy them up.
          </span>
        )}
      </div>

      {selected && (
        <div className="rounded-2xl bg-white p-4 ring-1 ring-slate-200/70">
          <div className="mb-2 flex items-center gap-2">
            <input
              className={`${inputClass} font-medium`}
              value={title}
              onChange={(e) => onTitle(e.target.value)}
              placeholder="Note title"
              maxLength={200}
              aria-label="Note title"
            />
            <span className="shrink-0 text-xs text-slate-400" aria-live="polite">
              {saveState === 'saving' && 'Saving…'}
              {saveState === 'saved' && '✓ Saved'}
              {saveState === 'error' && (
                <span className="text-rose-600">Save failed</span>
              )}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPreview((p) => !p)}
              className="shrink-0"
            >
              {preview ? '✏️ Edit' : '👁 Preview'}
            </Button>
            <Button
              variant="danger"
              size="sm"
              onClick={() => void remove(selected)}
              className="shrink-0"
            >
              Delete
            </Button>
          </div>

          {preview ? (
            <div className="md min-h-40 rounded-xl border border-slate-200 bg-slate-50/50 px-3 py-2">
              {content.trim() ? (
                <ReactMarkdown>{content}</ReactMarkdown>
              ) : (
                <p className="text-sm text-slate-400">Nothing to preview yet.</p>
              )}
            </div>
          ) : (
            <textarea
              className={`${inputClass} min-h-40 resize-y font-mono`}
              value={content}
              onChange={(e) => onContent(e.target.value)}
              placeholder="Write your notes in Markdown…"
              maxLength={20000}
              aria-label="Note content"
            />
          )}

          {/* enhance toolbar */}
          <div className="mt-3">
            <p className="mb-1.5 text-xs font-medium text-slate-500">
              Enhance with AI
            </p>
            <div className="flex flex-wrap gap-1.5">
              {ACTIONS.map((a) => (
                <Button
                  key={a.id}
                  variant="secondary"
                  size="sm"
                  disabled={busy !== null || !content.trim()}
                  onClick={() => void enhance(a.id)}
                >
                  {busy === a.id ? '…' : a.icon} {a.label}
                </Button>
              ))}
            </div>
          </div>

          {/* result panel */}
          {busy && (
            <div className="mt-3 rounded-xl border border-dashed border-slate-300 p-4">
              <Spinner label="Asking the AI…" />
            </div>
          )}
          {enhanced && !busy && (
            <div className="mt-3 rounded-xl bg-indigo-50/60 p-4 ring-1 ring-indigo-100">
              <div className="md">
                <ReactMarkdown>{enhanced.result}</ReactMarkdown>
              </div>
              {enhanced.cards && (
                <p className="mt-2 text-xs text-indigo-500">
                  {enhanced.cards.length} flashcards
                </p>
              )}
              <div className="mt-3 flex flex-wrap gap-2">
                <Button size="sm" onClick={append}>
                  ＋ Append to note
                </Button>
                <Button size="sm" variant="secondary" onClick={() => void copy()}>
                  {copied ? '✓ Copied' : '⧉ Copy'}
                </Button>
                <Button size="sm" variant="ghost" onClick={() => setEnhanced(null)}>
                  Dismiss
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {notes.length > 0 && !selected && (
        <p className="text-sm text-slate-400">
          Pick a note above, or create a new one.
        </p>
      )}
    </div>
  )
}
