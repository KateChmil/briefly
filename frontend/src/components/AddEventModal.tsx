import { useState } from 'react'
import { api } from '../api/client'
import { useSpaces } from '../lib/spaces'
import type { EventKind } from '../types'
import { Button, ErrorNote, Field, Modal, inputClass } from './ui'

interface Props {
  initialDate: string
  onClose: () => void
  onSaved: () => void
}

const KINDS: { value: EventKind; label: string }[] = [
  { value: 'class', label: '🎓 Class' },
  { value: 'exam', label: '🎯 Exam' },
  { value: 'other', label: '📌 Other' },
]

export default function AddEventModal({ initialDate, onClose, onSaved }: Props) {
  const { spaces } = useSpaces()
  const [title, setTitle] = useState('')
  const [date, setDate] = useState(initialDate)
  const [start, setStart] = useState('')
  const [end, setEnd] = useState('')
  const [kind, setKind] = useState<EventKind>('class')
  const [spaceId, setSpaceId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const save = async () => {
    if (!title.trim() || !date || busy) return
    setBusy(true)
    setError('')
    try {
      await api.createEvent({
        title: title.trim(),
        date,
        start_time: start || null,
        end_time: end || null,
        kind,
        space_id: spaceId || null,
      })
      onSaved()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not save the event')
      setBusy(false)
    }
  }

  return (
    <Modal title="Add to calendar" onClose={onClose}>
      <div className="space-y-3">
        <Field label="Title">
          <input
            autoFocus
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && save()}
            placeholder="e.g. Calculus lecture"
            className={inputClass}
          />
        </Field>
        <div className="flex gap-2">
          {KINDS.map((k) => (
            <button
              key={k.value}
              onClick={() => setKind(k.value)}
              className={`flex-1 rounded-xl px-2 py-2 text-sm font-medium ring-1 transition ${
                kind === k.value
                  ? 'bg-indigo-50 text-indigo-700 ring-indigo-300'
                  : 'bg-white text-slate-600 ring-slate-200 hover:bg-slate-50'
              }`}
            >
              {k.label}
            </button>
          ))}
        </div>
        <div className="grid grid-cols-3 gap-2">
          <Field label="Date">
            <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className={inputClass} />
          </Field>
          <Field label="Start">
            <input type="time" value={start} onChange={(e) => setStart(e.target.value)} className={inputClass} />
          </Field>
          <Field label="End">
            <input type="time" value={end} onChange={(e) => setEnd(e.target.value)} className={inputClass} />
          </Field>
        </div>
        <Field label="Subject (optional)">
          <select value={spaceId} onChange={(e) => setSpaceId(e.target.value)} className={inputClass}>
            <option value="">— none —</option>
            {spaces?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </Field>
        {error && <ErrorNote>{error}</ErrorNote>}
        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button onClick={save} disabled={!title.trim() || !date || busy}>
            {busy ? 'Saving…' : 'Add event'}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
