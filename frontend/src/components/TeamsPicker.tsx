import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { TeamsItem } from '../types'
import { Button, Spinner } from './ui'

interface Props {
  spaceId: string
  onClose: () => void
  onImported: () => Promise<unknown>
}

type Step =
  | { level: 'teams' }
  | { level: 'channels'; team: TeamsItem }
  | { level: 'files'; team: TeamsItem; channel: TeamsItem }

export default function TeamsPicker({ spaceId, onClose, onImported }: Props) {
  const [step, setStep] = useState<Step>({ level: 'teams' })
  const [items, setItems] = useState<TeamsItem[] | null>(null)
  const [selected, setSelected] = useState<Set<string>>(new Set())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    setItems(null)
    setError('')
    const load =
      step.level === 'teams'
        ? api.listTeams()
        : step.level === 'channels'
          ? api.listChannels(step.team.id)
          : api.listTeamsFiles(step.channel.id)
    load.then(setItems).catch((e) => setError(e.message))
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
      await api.importTeamsFiles(spaceId, [...selected])
      await onImported()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Import failed')
      setBusy(false)
    }
  }

  return (
    <div
      className="fixed inset-0 z-10 flex items-center justify-center bg-black/30"
      onClick={onClose}
    >
      <div
        className="flex h-96 w-full max-w-md flex-col rounded-xl bg-white p-5 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-center justify-between">
          <h2 className="font-semibold text-slate-900">
            {step.level === 'teams' && 'Microsoft Teams'}
            {step.level === 'channels' && step.team.name}
            {step.level === 'files' && step.channel.name}
          </h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600">
            ✕
          </button>
        </div>

        {step.level !== 'teams' && (
          <button
            className="mb-2 text-left text-xs text-indigo-600 hover:underline"
            onClick={() =>
              setStep(
                step.level === 'channels'
                  ? { level: 'teams' }
                  : { level: 'channels', team: step.team },
              )
            }
          >
            ← Back
          </button>
        )}

        <div className="min-h-0 flex-1 overflow-y-auto">
          {error && <p className="text-sm text-red-600">{error}</p>}
          {items === null ? (
            <Spinner label="Loading..." />
          ) : items.length === 0 ? (
            <p className="text-sm text-slate-400">Nothing here.</p>
          ) : (
            <ul className="space-y-1">
              {items.map((item) =>
                step.level === 'files' ? (
                  <li key={item.id}>
                    <label className="flex cursor-pointer items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-slate-50">
                      <input
                        type="checkbox"
                        checked={selected.has(item.id)}
                        onChange={() => toggle(item.id)}
                      />
                      <span className="truncate">{item.name}</span>
                    </label>
                  </li>
                ) : (
                  <li key={item.id}>
                    <button
                      className="w-full rounded-lg px-3 py-2 text-left text-sm hover:bg-slate-50"
                      onClick={() =>
                        step.level === 'teams'
                          ? setStep({ level: 'channels', team: item })
                          : setStep({
                              level: 'files',
                              team: step.team,
                              channel: item,
                            })
                      }
                    >
                      {step.level === 'teams' ? '👥 ' : '📁 '}
                      {item.name}
                    </button>
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
                ? 'Importing...'
                : `Import ${selected.size} file${selected.size === 1 ? '' : 's'}`}
            </Button>
          </div>
        )}
      </div>
    </div>
  )
}
