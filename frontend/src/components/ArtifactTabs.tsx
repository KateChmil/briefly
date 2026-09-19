import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { api } from '../api/client'
import type { Artifact, ArtifactKind, SpaceStatus, StudySession } from '../types'
import FlashcardsView from './FlashcardsView'
import PlanView from './PlanView'
import QuizView from './QuizView'
import { Button, ErrorNote, Spinner } from './ui'

interface Props {
  spaceId: string
  spaceName: string
  spaceStatus: SpaceStatus
  hasProfile: boolean
  artifacts: Artifact[]
  sessions: StudySession[]
  onToggleSession: (session: StudySession, done: boolean) => void
  onChanged: () => Promise<unknown>
  onGenerate: () => Promise<void>
}

const TABS: { kind: ArtifactKind; label: string; icon: string }[] = [
  { kind: 'study_plan', label: 'Plan', icon: '🗓️' },
  { kind: 'notes', label: 'Notes', icon: '📝' },
  { kind: 'sample_test', label: 'Test', icon: '🧪' },
  { kind: 'flashcards', label: 'Cards', icon: '🃏' },
]

function download(name: string, text: string) {
  const url = URL.createObjectURL(new Blob([text], { type: 'text/markdown' }))
  const a = document.createElement('a')
  a.href = url
  a.download = name
  a.click()
  URL.revokeObjectURL(url)
}

function GeneratingChecklist({ artifacts }: { artifacts: Artifact[] }) {
  return (
    <div className="animate-pop-in rounded-2xl bg-white p-6 ring-1 ring-slate-200/70">
      <p className="mb-4 text-sm font-semibold text-slate-800">
        Building your study materials…
      </p>
      <ul className="space-y-3">
        {TABS.map((t) => {
          const ready = artifacts.some((a) => a.kind === t.kind)
          return (
            <li key={t.kind} className="flex items-center gap-3 text-sm">
              <span className="w-5 text-center">
                {ready ? '✅' : <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-indigo-600 align-middle" />}
              </span>
              <span className={ready ? 'text-slate-800' : 'text-slate-500'}>
                {t.icon} {t.label}
              </span>
            </li>
          )
        })}
      </ul>
      <p className="mt-4 text-xs text-slate-400">This usually takes 10–20 seconds.</p>
    </div>
  )
}

export default function ArtifactTabs({
  spaceId,
  spaceName,
  spaceStatus,
  hasProfile,
  artifacts,
  sessions,
  onToggleSession,
  onChanged,
  onGenerate,
}: Props) {
  const [active, setActive] = useState<ArtifactKind>('study_plan')
  const [regenerating, setRegenerating] = useState(false)
  const [error, setError] = useState('')

  const generating = spaceStatus === 'generating'
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

  const body = () => {
    if (regenerating) return <Spinner label="Regenerating…" />
    if (generating && artifacts.length === 0) return <GeneratingChecklist artifacts={artifacts} />
    if (!artifact) {
      if (generating) {
        return (
          <div className="rounded-2xl border border-dashed border-slate-300 p-8 text-center">
            <Spinner label="Almost there…" />
          </div>
        )
      }
      return (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white/60 p-8 text-center">
          <div className="mb-2 text-3xl">✨</div>
          {hasProfile ? (
            <>
              <p className="mb-3 text-sm text-slate-600">
                Your profile is saved but nothing has been generated yet.
              </p>
              <Button onClick={() => void onGenerate()}>Generate my study materials</Button>
            </>
          ) : (
            <p className="text-sm text-slate-500">
              Finish the chat interview and your plan, notes, test and flashcards will
              appear here.
            </p>
          )}
        </div>
      )
    }
    switch (artifact.kind) {
      case 'study_plan':
        return (
          <PlanView
            spaceId={spaceId}
            content={artifact.content}
            sessions={sessions}
            onToggle={onToggleSession}
          />
        )
      case 'sample_test':
        return <QuizView key={artifact.id} content={artifact.content} />
      case 'flashcards':
        return <FlashcardsView content={artifact.content} />
      default:
        return (
          <div className="rounded-2xl bg-white p-5 ring-1 ring-slate-200/70">
            <div className="md">
              <ReactMarkdown>{artifact.content}</ReactMarkdown>
            </div>
          </div>
        )
    }
  }

  return (
    <div className="flex min-h-full flex-col">
      <div className="sticky top-0 z-10 flex items-center gap-1 overflow-x-auto border-b border-slate-200 bg-white/90 px-3 py-2 backdrop-blur">
        {TABS.map((t) => {
          const missing = generating && !artifacts.some((a) => a.kind === t.kind)
          return (
            <button
              key={t.kind}
              onClick={() => setActive(t.kind)}
              className={`flex shrink-0 items-center gap-1.5 rounded-xl px-3 py-1.5 text-sm font-medium transition ${
                active === t.kind
                  ? 'bg-indigo-100 text-indigo-700'
                  : 'text-slate-500 hover:bg-slate-100'
              }`}
            >
              <span aria-hidden>{t.icon}</span>
              {t.label}
              {missing && (
                <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-indigo-500" aria-label="generating" />
              )}
            </button>
          )
        })}
        <div className="ml-auto flex shrink-0 gap-1 pl-2">
          {active === 'notes' && artifact && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => download(`${spaceName} notes.md`, artifact.content)}
            >
              ⬇ .md
            </Button>
          )}
          <Button
            variant="secondary"
            size="sm"
            disabled={regenerating || generating || spaceStatus !== 'ready'}
            onClick={regenerate}
          >
            {regenerating ? 'Working…' : '↻ Regenerate'}
          </Button>
        </div>
      </div>

      <div className="flex-1 p-4">
        {error && <div className="mb-3"><ErrorNote>{error}</ErrorNote></div>}
        {generating && artifacts.length > 0 && (
          <div className="mb-3 flex items-center gap-2 rounded-xl bg-indigo-50 px-3 py-2 text-sm text-indigo-700 ring-1 ring-indigo-100">
            <div className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-indigo-200 border-t-indigo-600" />
            Updating your study plan…
          </div>
        )}
        {body()}
      </div>
    </div>
  )
}
