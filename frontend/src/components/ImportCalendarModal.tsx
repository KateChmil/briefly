import { useRef, useState } from 'react'
import { api } from '../api/client'
import { useSpaces } from '../lib/spaces'
import { Button, ErrorNote, Field, Modal, inputClass } from './ui'

interface Props {
  onClose: () => void
  onImported: () => void
}

export default function ImportCalendarModal({ onClose, onImported }: Props) {
  const { spaces } = useSpaces()
  const [tab, setTab] = useState<'link' | 'file'>('link')
  const [url, setUrl] = useState('')
  const [spaceId, setSpaceId] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [result, setResult] = useState<{ imported: number; skipped: number } | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const run = async (job: () => Promise<{ imported: number; skipped: number }>) => {
    setBusy(true)
    setError('')
    try {
      setResult(await job())
      onImported()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Import failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title="Import a calendar" onClose={onClose}>
      <div className="mb-4 flex rounded-xl bg-slate-100 p-1 text-sm font-medium">
        {(
          [
            ['link', '🔗 Canvas / calendar link'],
            ['file', '📄 .ics file'],
          ] as const
        ).map(([id, label]) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex-1 rounded-lg px-3 py-1.5 transition ${
              tab === id ? 'bg-white text-indigo-700 shadow-sm' : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="space-y-3">
        {tab === 'link' ? (
          <>
            <p className="text-sm text-slate-500">
              In Canvas open <b>Calendar → Calendar Feed</b> and copy the link. Outlook and
              Google Calendar offer a similar “publish / secret address in iCal format” link.
            </p>
            <Field label="Calendar feed URL">
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://canvas.university.edu/feeds/calendars/user_….ics"
                className={inputClass}
              />
            </Field>
          </>
        ) : (
          <p className="text-sm text-slate-500">
            Export your class schedule from Outlook, Teams or Google Calendar as an{' '}
            <b>.ics</b> file and upload it. Weekly repeating classes are expanded for you.
          </p>
        )}

        <Field label="Attach to subject (optional)">
          <select value={spaceId} onChange={(e) => setSpaceId(e.target.value)} className={inputClass}>
            <option value="">— all subjects —</option>
            {spaces?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
        </Field>

        {error && <ErrorNote>{error}</ErrorNote>}
        {result && (
          <div className="rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-700 ring-1 ring-emerald-200">
            ✅ Imported {result.imported} event{result.imported === 1 ? '' : 's'}
            {result.skipped > 0 && ` (${result.skipped} skipped: duplicates or out of range)`}.
          </div>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <Button variant="ghost" onClick={onClose}>
            {result ? 'Done' : 'Cancel'}
          </Button>
          {tab === 'link' ? (
            <Button
              disabled={!url.trim() || busy}
              onClick={() => run(() => api.importCalendarUrl(url.trim(), spaceId || undefined))}
            >
              {busy ? 'Importing…' : 'Import feed'}
            </Button>
          ) : (
            <>
              <input
                ref={fileInput}
                type="file"
                hidden
                accept=".ics,text/calendar"
                onChange={(e) => {
                  const file = e.target.files?.[0]
                  if (file) void run(() => api.importCalendarFile(file, spaceId || undefined))
                  e.target.value = ''
                }}
              />
              <Button disabled={busy} onClick={() => fileInput.current?.click()}>
                {busy ? 'Importing…' : 'Choose .ics file'}
              </Button>
            </>
          )}
        </div>
      </div>
    </Modal>
  )
}
