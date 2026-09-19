import { useRef, useState } from 'react'
import { api } from '../api/client'
import type { Source } from '../types'
import CanvasPicker from './CanvasPicker'
import TeamsPicker from './TeamsPicker'
import { Badge, Button, ErrorNote } from './ui'

interface Props {
  spaceId: string
  sources: Source[]
  onChanged: () => Promise<unknown>
}

const ICONS: Record<string, string> = {
  pdf: '📕',
  docx: '📘',
  pptx: '📙',
  txt: '📄',
  md: '📄',
  csv: '📊',
}
const iconFor = (filename: string) =>
  ICONS[filename.split('.').pop()?.toLowerCase() ?? ''] ?? '📄'

export default function SourceList({ spaceId, sources, onChanged }: Props) {
  const fileInput = useRef<HTMLInputElement>(null)
  const [teamsOpen, setTeamsOpen] = useState(false)
  const [canvasOpen, setCanvasOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [dragging, setDragging] = useState(false)
  const [error, setError] = useState('')

  const uploadAll = async (files: FileList | File[]) => {
    setBusy(true)
    setError('')
    const failures: string[] = []
    for (const file of Array.from(files)) {
      try {
        await api.uploadSource(spaceId, file)
      } catch (e) {
        failures.push(`${file.name}: ${e instanceof Error ? e.message : 'upload failed'}`)
      }
    }
    await onChanged()
    if (failures.length) setError(failures.join('\n'))
    setBusy(false)
    if (fileInput.current) fileInput.current.value = ''
  }

  const remove = async (id: string) => {
    try {
      await api.deleteSource(spaceId, id)
      await onChanged()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not remove the file')
    }
  }

  return (
    <div className="flex flex-col gap-3 p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-800">Materials</h2>
        <Badge>{sources.length}</Badge>
      </div>

      <div
        onDragOver={(e) => {
          e.preventDefault()
          setDragging(true)
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault()
          setDragging(false)
          if (e.dataTransfer.files.length) void uploadAll(e.dataTransfer.files)
        }}
        onClick={() => fileInput.current?.click()}
        role="button"
        tabIndex={0}
        onKeyDown={(e) => (e.key === 'Enter' || e.key === ' ') && fileInput.current?.click()}
        className={`cursor-pointer rounded-xl border-2 border-dashed px-3 py-5 text-center transition ${
          dragging
            ? 'border-indigo-400 bg-indigo-50'
            : 'border-slate-300 bg-white hover:border-indigo-300 hover:bg-indigo-50/40'
        }`}
      >
        <div className="text-2xl">{busy ? '⏳' : '📥'}</div>
        <p className="mt-1 text-sm font-medium text-slate-700">
          {busy ? 'Reading files…' : 'Drop files or click to upload'}
        </p>
        <p className="text-xs text-slate-400">PDF, Word, PowerPoint, text</p>
        <input
          ref={fileInput}
          type="file"
          multiple
          hidden
          accept=".pdf,.docx,.pptx,.txt,.md,.csv"
          onChange={(e) => e.target.files?.length && void uploadAll(e.target.files)}
        />
      </div>

      <Button variant="secondary" onClick={() => setTeamsOpen(true)}>
        <span aria-hidden>👥</span> Import from Microsoft Teams
      </Button>

      <Button variant="secondary" onClick={() => setCanvasOpen(true)}>
        <span aria-hidden>🎓</span> Import from Canvas
      </Button>

      {error && (
        <div className="whitespace-pre-line">
          <ErrorNote>{error}</ErrorNote>
        </div>
      )}

      <ul className="space-y-1.5">
        {sources.map((s) => (
          <li
            key={s.id}
            className="group flex items-center gap-2.5 rounded-xl bg-white px-3 py-2 shadow-sm ring-1 ring-slate-200/70"
          >
            <span className="text-lg" aria-hidden>
              {iconFor(s.filename)}
            </span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-slate-800" title={s.filename}>
                {s.filename}
              </p>
              <p className="text-xs text-slate-400">
                {s.origin === 'teams'
                  ? 'Microsoft Teams'
                  : s.origin === 'canvas'
                    ? 'Canvas'
                    : 'Uploaded'}
              </p>
            </div>
            <button
              onClick={() => remove(s.id)}
              className="hidden rounded p-0.5 text-slate-300 hover:bg-rose-50 hover:text-rose-600 group-hover:block"
              title="Remove"
              aria-label={`Remove ${s.filename}`}
            >
              ✕
            </button>
          </li>
        ))}
        {sources.length === 0 && (
          <li className="px-2 py-3 text-center text-xs text-slate-400">
            No materials yet — your plan works better with them.
          </li>
        )}
      </ul>

      {teamsOpen && (
        <TeamsPicker
          spaceId={spaceId}
          onClose={() => setTeamsOpen(false)}
          onImported={async () => {
            setTeamsOpen(false)
            await onChanged()
          }}
        />
      )}

      {canvasOpen && (
        <CanvasPicker
          spaceId={spaceId}
          onClose={() => setCanvasOpen(false)}
          onImported={async () => {
            setCanvasOpen(false)
            await onChanged()
          }}
        />
      )}
    </div>
  )
}
