import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { api } from '../api/client'
import type { Artifact, ArtifactKind, SpaceStatus } from '../types'
import QuizView from './QuizView'
import { Button, Spinner } from './ui'

interface Props {
  spaceId: string
  spaceStatus: SpaceStatus
  artifacts: Artifact[]
  onChanged: () => Promise<unknown>
}

const TABS: { kind: ArtifactKind; label: string }[] = [
  { kind: 'study_plan', label: 'Study plan' },
  { kind: 'notes', label: 'Notes' },
  { kind: 'sample_test', label: 'Sample test' },
]

export default function ArtifactTabs({
  spaceId,
  spaceStatus,
  artifacts,
  onChanged,
}: Props) {
  const [active, setActive] = useState<ArtifactKind>('study_plan')
  const [regenerating, setRegenerating] = useState(false)
  const [error, setError] = useState('')

  const artifact = artifacts.find((a) => a.kind === active)

  const regenerate = async () => {
    setRegenerating(true)
    setError('')
    try {
      await api.regenerateArtifact(spaceId, active)
      await onChanged()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Regeneration failed')
    } finally {
      setRegenerating(false)
    }
  }

  return (
    <div className="flex min-h-full flex-col">
      <div className="flex items-center gap-1 border-b border-slate-200 bg-white px-3 py-2">
        {TABS.map((t) => (
          <button
            key={t.kind}
            onClick={() => setActive(t.kind)}
            className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
              active === t.kind
                ? 'bg-indigo-100 text-indigo-700'
                : 'text-slate-500 hover:bg-slate-100'
            }`}
          >
            {t.label}
          </button>
        ))}
        <div className="ml-auto">
          <Button
            variant="ghost"
            className="text-xs"
            disabled={regenerating || spaceStatus !== 'ready'}
            onClick={regenerate}
          >
            {regenerating ? 'Working...' : 'Regenerate'}
          </Button>
        </div>
      </div>

      <div className="flex-1 p-4">
        {error && <p className="mb-2 text-sm text-red-600">{error}</p>}
        {regenerating ? (
          <Spinner label="Regenerating..." />
        ) : !artifact ? (
          <div className="rounded-lg border border-dashed border-slate-300 p-6 text-center text-sm text-slate-400">
            {spaceStatus === 'ready'
              ? 'Nothing generated yet — hit Regenerate.'
              : 'Finish the chat interview and your materials will appear here.'}
          </div>
        ) : artifact.kind === 'sample_test' && artifact.format === 'json' ? (
          <QuizView content={artifact.content} />
        ) : (
          <div className="prose-sm max-w-none text-slate-800 [&_h1]:text-lg [&_h2]:text-base [&_h3]:text-sm [&_li]:my-0.5 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5">
            <ReactMarkdown>{artifact.content}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  )
}
