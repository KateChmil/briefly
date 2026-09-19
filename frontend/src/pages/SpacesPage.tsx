import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import type { SpaceSummary, SpaceStatus } from '../types'
import { Badge, Button, Spinner } from '../components/ui'

const STATUS_LABEL: Record<SpaceStatus, string> = {
  interviewing: 'Setting up',
  generating: 'Generating',
  ready: 'Ready',
}

export default function SpacesPage() {
  const [spaces, setSpaces] = useState<SpaceSummary[] | null>(null)
  const [showCreate, setShowCreate] = useState(false)
  const [name, setName] = useState('')
  const [error, setError] = useState('')
  const navigate = useNavigate()

  const load = () => api.listSpaces().then(setSpaces).catch((e) => setError(e.message))
  useEffect(() => {
    load()
  }, [])

  const create = async () => {
    if (!name.trim()) return
    try {
      const space = await api.createSpace(name.trim())
      navigate(`/spaces/${space.id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create space')
    }
  }

  const remove = async (id: string) => {
    await api.deleteSpace(id)
    load()
  }

  return (
    <div className="mx-auto max-w-4xl p-8">
      <div className="mb-8 flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-slate-900">Briefly</h1>
          <p className="text-slate-500">Your AI study spaces</p>
        </div>
        <Button onClick={() => setShowCreate(true)}>+ New subject space</Button>
      </div>

      {error && <p className="mb-4 text-sm text-red-600">{error}</p>}

      {spaces === null ? (
        <Spinner label="Loading spaces..." />
      ) : spaces.length === 0 ? (
        <div className="rounded-xl border border-dashed border-slate-300 p-12 text-center text-slate-500">
          No spaces yet. Create your first subject space to get started.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {spaces.map((s) => (
            <div
              key={s.id}
              className="group relative rounded-xl border border-slate-200 bg-white p-5 shadow-sm hover:shadow-md"
            >
              <Link to={`/spaces/${s.id}`} className="block">
                <div className="mb-2 flex items-center justify-between">
                  <h2 className="font-semibold text-slate-900">{s.name}</h2>
                  <Badge>{STATUS_LABEL[s.status]}</Badge>
                </div>
                <p className="text-sm text-slate-500">
                  {s.source_count} source{s.source_count !== 1 && 's'} ·{' '}
                  {s.artifact_count} artifact{s.artifact_count !== 1 && 's'}
                </p>
              </Link>
              <button
                onClick={() => remove(s.id)}
                className="absolute right-3 top-3 hidden rounded p-1 text-slate-400 hover:bg-red-50 hover:text-red-600 group-hover:block"
                title="Delete space"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      {showCreate && (
        <div
          className="fixed inset-0 z-10 flex items-center justify-center bg-black/30"
          onClick={() => setShowCreate(false)}
        >
          <div
            className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl"
            onClick={(e) => e.stopPropagation()}
          >
            <h2 className="mb-4 text-lg font-semibold">New subject space</h2>
            <input
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && create()}
              placeholder="e.g. Biology 101, Calculus II..."
              className="mb-4 w-full rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-indigo-500"
            />
            <div className="flex justify-end gap-2">
              <Button variant="ghost" onClick={() => setShowCreate(false)}>
                Cancel
              </Button>
              <Button onClick={create} disabled={!name.trim()}>
                Create
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
