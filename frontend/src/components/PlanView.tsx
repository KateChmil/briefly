import { useCallback, useEffect, useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import { api } from '../api/client'
import { formatMinutes, formatShort, formatWeekday, todayISO, weekStart } from '../lib/dates'
import { kindStyle } from '../lib/theme'
import type { PlanContent, RescheduleResult, SpaceProgress, StudySession } from '../types'
import { CatchUpBanner, summarize } from './CatchUp'
import { Badge, ProgressBar } from './ui'

interface Props {
  spaceId: string
  /** The plan artifact's content: JSON `{overview, sessions}` or legacy Markdown. */
  content: string
  sessions: StudySession[]
  onToggle: (session: StudySession, done: boolean) => void
}

function parsePlan(content: string): PlanContent | null {
  try {
    const parsed = JSON.parse(content)
    if (parsed && typeof parsed === 'object' && Array.isArray(parsed.sessions)) {
      return { overview: String(parsed.overview ?? ''), sessions: parsed.sessions }
    }
  } catch {
    /* legacy plans were plain Markdown */
  }
  return null
}

export default function PlanView({ spaceId, content, sessions, onToggle }: Props) {
  const plan = useMemo(() => parsePlan(content), [content])
  const today = todayISO()

  const [progress, setProgress] = useState<SpaceProgress | null>(null)
  const [dateOverrides, setDateOverrides] = useState<ReadonlyMap<number, string>>(new Map())
  const [catchupNote, setCatchupNote] = useState('')

  const refreshProgress = useCallback(() => {
    api.getProgress(spaceId).then(setProgress).catch(() => setProgress(null))
  }, [spaceId])

  useEffect(() => {
    refreshProgress()
  }, [refreshProgress, sessions])

  const onRescheduled = (res: RescheduleResult) => {
    setDateOverrides(new Map(res.sessions.map((s) => [s.id, s.date])))
    setCatchupNote(summarize(res))
    refreshProgress()
  }

  // Show the new dates right away even though the parent still holds the
  // pre-reschedule list; done flags keep coming from the parent's sessions.
  const shown = useMemo(
    () =>
      sessions.map((s) =>
        dateOverrides.has(s.id) ? { ...s, date: dateOverrides.get(s.id)! } : s,
      ),
    [sessions, dateOverrides],
  )

  const weeks = useMemo(() => {
    const groups = new Map<string, StudySession[]>()
    for (const s of shown) {
      const key = weekStart(s.date)
      groups.set(key, [...(groups.get(key) ?? []), s])
    }
    return [...groups.entries()].sort(([a], [b]) => a.localeCompare(b))
  }, [shown])

  if (!plan) {
    // Older, Markdown-only plan: still readable, just not checkable.
    return (
      <div className="md">
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    )
  }

  const done = shown.filter((s) => s.done).length
  const minutesLeft = shown.filter((s) => !s.done).reduce((n, s) => n + s.minutes, 0)
  const next = shown.find((s) => !s.done && s.date >= today)

  return (
    <div className="space-y-4">
      <div className="rounded-2xl bg-gradient-to-br from-indigo-50 to-violet-50 p-4 ring-1 ring-indigo-100">
        <div className="mb-2 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <p className="text-sm font-semibold text-slate-800">
              {done}/{shown.length} sessions done
            </p>
            {progress && (
              <Badge
                className={
                  progress.on_track
                    ? 'bg-emerald-50 text-emerald-700 ring-emerald-200'
                    : 'bg-amber-50 text-amber-700 ring-amber-200'
                }
              >
                {progress.on_track ? 'On track' : 'Behind'}
              </Badge>
            )}
          </div>
          <span className="text-xs text-slate-500">{formatMinutes(minutesLeft)} left</span>
        </div>
        <ProgressBar value={done} max={sessions.length} />
        <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
          <p className="text-xs text-slate-600">
            {next ? (
              <>Up next: <b>{next.title}</b> · {formatShort(next.date)}</>
            ) : sessions.length > 0 && done === sessions.length ? (
              '🎉 You finished the whole plan!'
            ) : (
              'No upcoming sessions.'
            )}
          </p>
          <a
            href={api.exportUrl(spaceId)}
            className="text-xs font-medium text-indigo-600 hover:underline"
          >
            ⬆ Add to my calendar (.ics)
          </a>
        </div>
      </div>

      {progress && progress.overdue > 0 && (
        <CatchUpBanner
          spaceId={spaceId}
          overdue={progress.overdue}
          onRescheduled={onRescheduled}
        />
      )}
      {catchupNote && (
        <p className="rounded-xl bg-emerald-50 px-3 py-2 text-sm text-emerald-700 ring-1 ring-emerald-200">
          {catchupNote}
        </p>
      )}

      {plan.overview && (
        <details className="group rounded-2xl bg-white p-4 ring-1 ring-slate-200/70" open>
          <summary className="cursor-pointer select-none text-sm font-semibold text-slate-800">
            Strategy
          </summary>
          <div className="md mt-2">
            <ReactMarkdown>{plan.overview}</ReactMarkdown>
          </div>
        </details>
      )}

      {weeks.map(([start, list]) => (
        <section key={start}>
          <h3 className="mb-1.5 px-1 text-xs font-semibold uppercase tracking-wide text-slate-400">
            Week of {formatShort(start)}
          </h3>
          <ul className="space-y-1.5">
            {list.map((s) => {
              const style = kindStyle(s.kind)
              const isToday = s.date === today
              const overdue = s.date < today && !s.done
              return (
                <li
                  key={s.id}
                  className={`flex items-start gap-3 rounded-xl px-3 py-2.5 ring-1 transition ${
                    isToday
                      ? 'bg-indigo-50 ring-indigo-200'
                      : overdue
                        ? 'bg-amber-50/60 ring-amber-200'
                        : 'bg-white ring-slate-200/70'
                  } ${s.done ? 'opacity-60' : ''}`}
                >
                  <button
                    role="checkbox"
                    aria-checked={s.done}
                    aria-label={`Mark "${s.title}" ${s.done ? 'not done' : 'done'}`}
                    onClick={() => onToggle(s, !s.done)}
                    className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border-2 text-xs font-bold transition ${
                      s.done
                        ? 'border-emerald-500 bg-emerald-500 text-white'
                        : 'border-slate-300 bg-white text-transparent hover:border-emerald-400'
                    }`}
                  >
                    ✓
                  </button>
                  <div className="w-12 shrink-0 text-center leading-tight">
                    <p className="text-[11px] font-medium uppercase text-slate-400">
                      {formatWeekday(s.date)}
                    </p>
                    <p className="text-sm font-semibold text-slate-800">{formatShort(s.date)}</p>
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className={`text-sm font-medium text-slate-800 ${s.done ? 'line-through' : ''}`}>
                      {s.title}
                    </p>
                    {s.topic && <p className="text-xs text-slate-500">{s.topic}</p>}
                  </div>
                  <div className="flex shrink-0 flex-col items-end gap-1">
                    <Badge className={style.chip}>{style.label}</Badge>
                    <span className="text-xs text-slate-400">{formatMinutes(s.minutes)}</span>
                  </div>
                </li>
              )
            })}
          </ul>
        </section>
      ))}
    </div>
  )
}
