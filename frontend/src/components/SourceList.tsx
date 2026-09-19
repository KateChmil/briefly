import { useRef, useState } from 'react'
import { api } from '../api/client'
import type { Source } from '../types'
import TeamsPicker from './TeamsPicker'
import { Badge, Button } from './ui'

interface Props {
  spaceId: string
  sources: Source[]
  onChanged: () => Promise<unknown>
}

export default function SourceList({ spaceId, sources, onChanged }: Props) {
  const fileInput = useRef<HTMLInputElement>(null)
  const [teamsOpen, setTeamsOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const upload = async (file: File) => {
    setBusy(true)
    setError('')
    try {
      await api.uploadSource(spaceId, file)
      await onChanged()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Upload failed')
    } finally {
      setBusy(false)
      if (fileInput.current) fileInput.current.value = ''
    }
  }

  const remove = async (id: string) => {
    await api.deleteSource(spaceId, id)
    await onChanged()
  }

  return (
    <div className="flex flex-col gap-3 p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-700">Sources</h2>
        <Badge>{sources.length}</Badge>
      </div>

      <div className="flex flex-col gap-2">
        <Button
          variant="ghost"
          disabled={busy}
          onClick={() => fileInput.current?.click()}
        >
          {busy ? 'Uploading...' : 'Upload file'}
        </Button>
        <Button variant="ghost" onClick={() => setTeamsOpen(true)}>
          Import from Teams
        </Button>
        <input
          ref={fileInput}
          type="file"
          hidden
          accept=".pdf,.docx,.pptx,.txt,.md,.csv"
          onChange={(e) => e.target.files?.[0] && upload(e.target.files[0])}
        />
      </div>

      {error && <p className="text-xs text-red-600">{error}</p>}

      <ul className="space-y-1">
        {sources.map((s) => (
          <li
            key={s.id}
            className="group flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-2"
          >
            <span className="text-slate-400">📄</span>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm text-slate-800">{s.filename}</p>
              <p className="text-xs text-slate-400">
                {s.origin === 'teams' ? 'Microsoft Teams' : 'Uploaded'}
              </p>
            </div>
            <button
              onClick={() => remove(s.id)}
              className="hidden text-slate-400 hover:text-red-600 group-hover:block"
              title="Remove"
            >
              ✕
            </button>
          </li>
        ))}
        {sources.length === 0 && (
          <li className="rounded-lg border border-dashed border-slate-300 p-4 text-center text-xs text-slate-400">
            No sources yet. Upload files or import from Teams.
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
    </div>
  )
}
