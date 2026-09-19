import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { CanvasItem } from '../types'
import { Button, ErrorNote, Modal, Spinner } from './ui'

interface Props {
  spaceId: string
  onClose: () => void
  onImported: () => Promise<unknown>
}

type Step = { level: 'courses' } | { level: 'files'; course: CanvasItem }

export default function CanvasPicker({ spaceId, onClose, onImported }: Props) {
  const [step, setStep] = useState<Step>({ level: 'courses' })
  const [items, setItems] = useState<CanvasItem[] | null>(null)
  const [mode, setMode] = useState<'mock' | 'live' | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [busy, setBusy] = useState(false)
  const [dueBusy, setDueBusy] = useState<string | null>(null)
  const [notice, setNotice] = useState('')
  const [error, setError] = useState('')

  useEffect(() => {
    let cancelled = false
    api
      .getCanvasStatus()
      .then((s) => !cancelled && setMode(s.mode))
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [])

  useEffect(() => {
    let cancelled = false
    setItems(null)
    setError('')
    const load =
      step.level === 'courses'
        ? api.listCanvasCourses()
        : api.listCanvasFiles(step.course.id)
    load
      .then((r) => !cancelled && setItems(r))
      .catch(
        (e) =>
          !cancelled &&
          setError(e instanceof Error ? e.message : 'Could not load Canvas'),
      )
    return () => {
      cancelled = true
    }
  }, [step])

  const toggle = (id: string) =>
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const importFiles = async () => {
    setBusy(true)
    setError('')
    try {
      const result = await api.importCanvasFiles(spaceId, [...selected])
      if (result.skipped.length && result.imported.length === 0) {
        setError(`Nothing imported: ${result.skipped[0].reason}`)
        setBusy(false)
        return
      }
      await onImported()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Import failed')
      setBusy(false)
    }
  }

  const addDueDates = async (course: CanvasItem) => {
    setDueBusy(course.id)
    setError('')
    setNotice('')
    try {
      const r = await api.importCanvasAssignments(spaceId, course.id)
      setNotice(
        r.imported > 0
          ? `Added ${r.imported} due date${r.imported === 1 ? '' : 's'} from ${course.name} to your calendar${r.skipped ? ` (${r.skipped} skipped)` : ''}.`
          : `No new due dates in ${course.name}.`,
      )
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not import due dates')
    } finally {
      setDueBusy(null)
    }
  }

  return (
    <Modal
      title={step.level === 'courses' ? 'Canvas' : step.course.name}
      onClose={onClose}
    >
      <div className="flex h-72 flex-col">
        {mode === 'mock' && (
          <p className="mb-2 text-xs text-slate-400">
            Demo data — connect a real Canvas with CANVAS_BASE_URL + CANVAS_TOKEN.
          </p>
        )}
        {step.level === 'files' && (
          <button
            className="mb-2 self-start text-xs font-medium text-indigo-600 hover:underline"
            onClick={() => setStep({ level: 'courses' })}
          >
            ← Back
          </button>
        )}

        <div className="min-h-0 flex-1 overflow-y-auto">
          {error && <ErrorNote>{error}</ErrorNote>}
          {notice && (
            <p className="mb-2 rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-700 ring-1 ring-emerald-200">
              {notice}
            </p>
          )}
          {items === null && !error ? (
            <Spinner label="Loading…" />
          ) : items?.length === 0 ? (
            <p className="text-sm text-slate-400">Nothing here.</p>
          ) : (
            <ul className="space-y-1">
              {items?.map((item) =>
                step.level === 'files' ? (
                  <li key={item.id}>
                    <label className="flex cursor-pointer items-center gap-2.5 rounded-xl px-3 py-2 text-sm transition hover:bg-slate-50">
                      <input
                        type="checkbox"
                        className="h-4 w-4 rounded accent-indigo-600"
                        checked={selected.has(item.id)}
                        onChange={() => toggle(item.id)}
                      />
                      <span className="truncate">{item.name}</span>
                    </label>
                  </li>
                ) : (
                  <li key={item.id} className="flex items-center gap-1.5">
                    <button
                      className="flex min-w-0 flex-1 items-center gap-2 rounded-xl px-3 py-2 text-left text-sm transition hover:bg-slate-50"
                      onClick={() => setStep({ level: 'files', course: item })}
                    >
                      <span aria-hidden>🎓</span>
                      <span className="truncate">{item.name}</span>
                      <span
                        className="ml-auto shrink-0 text-slate-300"
                        aria-hidden
                      >
                        ›
                      </span>
                    </button>
                    <Button
                      variant="secondary"
                      size="sm"
                      className="shrink-0"
                      disabled={dueBusy !== null}
                      onClick={() => addDueDates(item)}
                      title={`Add ${item.name} assignment due dates to the calendar`}
                    >
                      {dueBusy === item.id ? 'Adding…' : '＋ Due dates'}
                    </Button>
                  </li>
                ),
              )}
            </ul>
          )}
        </div>

        {step.level === 'files' && (
          <div className="mt-3 flex justify-end border-t border-slate-100 pt-3">
            <Button onClick={importFiles} disabled={selected.size === 0 || busy}>
              {busy
                ? 'Importing…'
                : `Import ${selected.size} file${selected.size === 1 ? '' : 's'}`}
            </Button>
          </div>
        )}
      </div>
    </Modal>
  )
}
