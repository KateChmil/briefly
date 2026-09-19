import { useEffect, useState } from 'react'
import { api } from '../api/client'
import type { TeamsItem } from '../types'
import { Button, ErrorNote, Modal, Spinner } from './ui'

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
    let cancelled = false
    setItems(null)
    setError('')
    const load =
      step.level === 'teams'
        ? api.listTeams()
        : step.level === 'channels'
          ? api.listChannels(step.team.id)
          : api.listTeamsFiles(step.channel.id)
    load
      .then((r) => !cancelled && setItems(r))
      .catch((e) => !cancelled && setError(e.message))
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
      const result = await api.importTeamsFiles(spaceId, [...selected])
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

  const title =
    step.level === 'teams'
      ? 'Microsoft Teams'
      : step.level === 'channels'
        ? step.team.name
        : `${step.team.name} › ${step.channel.name}`

  return (
    <Modal title={title} onClose={onClose}>
      <div className="flex h-72 flex-col">
        <p className="mb-2 text-xs text-slate-400">Demo data — a real Teams connection plugs in here.</p>
        {step.level !== 'teams' && (
          <button
            className="mb-2 self-start text-xs font-medium text-indigo-600 hover:underline"
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
          {error && <ErrorNote>{error}</ErrorNote>}
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
                  <li key={item.id}>
                    <button
                      className="flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm transition hover:bg-slate-50"
                      onClick={() =>
                        step.level === 'teams'
                          ? setStep({ level: 'channels', team: item })
                          : setStep({ level: 'files', team: step.team, channel: item })
                      }
                    >
                      <span aria-hidden>{step.level === 'teams' ? '👥' : '📁'}</span>
                      {item.name}
                      <span className="ml-auto text-slate-300">›</span>
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
                ? 'Importing…'
                : `Import ${selected.size} file${selected.size === 1 ? '' : 's'}`}
            </Button>
          </div>
        )}
      </div>
    </Modal>
  )
}
