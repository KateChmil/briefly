import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../api/client'
import CalendarRow, { sessionIdOf } from '../components/CalendarRow'
import { RescheduleButton } from '../components/CatchUp'
import { Badge, Button, Card, Countdown, ErrorNote, ProgressBar, Spinner } from '../components/ui'
import {
  addDays,
  countdownLabel,
  daysUntil,
  formatLong,
  greeting,
  todayISO,
  weekStart,
} from '../lib/dates'
import { useSpaces } from '../lib/spaces'
import { spaceColor } from '../lib/theme'
import type { CalendarItem, SpaceStatus } from '../types'

const STATUS: Record<SpaceStatus, { label: string; tone: string }> = {
  interviewing: { label: 'Setting up', tone: 'bg-amber-50 text-amber-700 ring-amber-200' },
  generating: { label: 'Generating', tone: 'bg-indigo-50 text-indigo-700 ring-indigo-200' },
  ready: { label: 'Ready', tone: 'bg-emerald-50 text-emerald-700 ring-emerald-200' },
}

function Stat({
  icon,
  label,
  value,
  hint,
}: {
  icon: string
  label: string
  value: string
  hint?: string
}) {
  return (
    <Card className="animate-slide-up p-4">
      <div className="flex items-center gap-3">
        <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-indigo-50 text-xl">
          {icon}
        </span>
        <div className="min-w-0">
          <p className="text-xs font-medium text-slate-500">{label}</p>
          <p className="truncate text-lg font-bold text-slate-900">{value}</p>
          {hint && <p className="truncate text-xs text-slate-500">{hint}</p>}
        </div>
      </div>
    </Card>
  )
}

export default function DashboardPage({ onNewSpace }: { onNewSpace: () => void }) {
  const { spaces, error: spacesError, reload } = useSpaces()
  const [items, setItems] = useState<CalendarItem[] | null>(null)
  const [error, setError] = useState('')
  const [catchupNote, setCatchupNote] = useState('')
  const today = todayISO()

  const loadItems = useCallback(async () => {
    try {
      setItems(await api.getCalendar(addDays(today, -14), addDays(today, 90)))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load your schedule')
      setItems([])
    }
  }, [today])

  useEffect(() => {
    void loadItems()
  }, [loadItems])

  const toggle = async (item: CalendarItem, done: boolean) => {
    // optimistic: tick immediately, roll back if the server refuses
    setItems((prev) => prev?.map((i) => (i.id === item.id ? { ...i, done } : i)) ?? prev)
    try {
      await api.setSessionDone(sessionIdOf(item), done)
      void reload() // refresh per-subject progress
    } catch (e) {
      setItems((prev) => prev?.map((i) => (i.id === item.id ? { ...i, done: !done } : i)) ?? prev)
      setError(e instanceof Error ? e.message : 'Could not update the session')
    }
  }

  const removeSpace = async (id: string, name: string) => {
    if (!window.confirm(`Delete "${name}" and everything in it?`)) return
    try {
      await api.deleteSpace(id)
      await Promise.all([reload(), loadItems()])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not delete the space')
    }
  }

  const view = useMemo(() => {
    const all = items ?? []
    const todays = all.filter((i) => i.date === today)
    const sessionsToday = todays.filter((i) => i.type === 'session')
    const weekFrom = weekStart(today)
    const weekTo = addDays(weekFrom, 6)
    const week = all.filter((i) => i.type === 'session' && i.date >= weekFrom && i.date <= weekTo)
    return {
      todays,
      todayDone: sessionsToday.filter((i) => i.done).length,
      todayTotal: sessionsToday.length,
      weekDone: week.filter((i) => i.done).length,
      weekTotal: week.length,
      overdue: all
        .filter((i) => i.type === 'session' && i.date < today && !i.done)
        .slice(-4),
      overdueSpaceIds: [
        ...new Set(
          all
            .filter((i) => i.type === 'session' && i.date < today && !i.done)
            .map((i) => i.space_id)
            .filter((x): x is string => !!x),
        ),
      ],
      upcoming: all.filter((i) => i.date > today && i.date <= addDays(today, 7)).slice(0, 8),
      exams: all.filter((i) => i.kind === 'exam' && i.date >= today).slice(0, 4),
    }
  }, [items, today])

  const nextExam = view.exams[0]

  if (spaces === null) {
    return (
      <div className="flex h-full items-center justify-center">
        {spacesError ? <ErrorNote>{spacesError}</ErrorNote> : <Spinner label="Loading…" />}
      </div>
    )
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 px-4 py-6 sm:px-8 sm:py-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 sm:text-3xl">
            {greeting()} 👋
          </h1>
          <p className="text-sm text-slate-500">{formatLong(today)}</p>
        </div>
        <Button onClick={onNewSpace}>+ New subject</Button>
      </div>

      {(error || spacesError) && <ErrorNote>{error || spacesError}</ErrorNote>}

      {spaces.length === 0 ? (
        <Card className="overflow-hidden">
          <div className="bg-gradient-to-br from-indigo-600 to-violet-600 px-8 py-10 text-white">
            <h2 className="text-2xl font-bold">Study smarter, not longer</h2>
            <p className="mt-2 max-w-xl text-indigo-100">
              Add a subject, bring in your materials from Teams or a file, and Briefly
              builds your study plan, calendar, notes, practice test and flashcards.
            </p>
            <Button variant="secondary" className="mt-5" onClick={onNewSpace}>
              Create your first subject
            </Button>
          </div>
          <div className="grid gap-4 p-6 sm:grid-cols-3">
            {[
              ['1', 'Add a subject', 'Name the course you are studying for.'],
              ['2', 'Chat with Briefly', 'Tell it your exam date, level and weekly hours.'],
              ['3', 'Get your plan', 'A dated plan, notes, a test and flashcards appear.'],
            ].map(([n, t, d]) => (
              <div key={n} className="flex gap-3">
                <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-indigo-50 text-sm font-bold text-indigo-600">
                  {n}
                </span>
                <div>
                  <p className="text-sm font-semibold text-slate-800">{t}</p>
                  <p className="text-sm text-slate-500">{d}</p>
                </div>
              </div>
            ))}
          </div>
        </Card>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-3">
            <Stat
              icon="🎯"
              label="Next exam"
              value={nextExam ? countdownLabel(daysUntil(nextExam.date)) : 'None set'}
              hint={nextExam?.space_name ?? 'Tell Briefly your exam date'}
            />
            <Stat
              icon="✅"
              label="Today"
              value={view.todayTotal ? `${view.todayDone}/${view.todayTotal} sessions` : 'Nothing planned'}
              hint={view.todayTotal && view.todayDone === view.todayTotal ? 'All done — nice!' : undefined}
            />
            <Stat
              icon="📈"
              label="This week"
              value={view.weekTotal ? `${Math.round((view.weekDone / view.weekTotal) * 100)}% complete` : '—'}
              hint={view.weekTotal ? `${view.weekDone} of ${view.weekTotal} sessions` : undefined}
            />
          </div>

          <div className="grid gap-6 lg:grid-cols-5">
            <Card className="p-4 lg:col-span-3">
              <div className="mb-2 flex items-center justify-between px-1">
                <h2 className="font-semibold text-slate-900">Today</h2>
                <Link to="/calendar" className="text-xs font-medium text-indigo-600 hover:underline">
                  Open calendar →
                </Link>
              </div>
              {items === null ? (
                <div className="p-4"><Spinner label="Loading schedule…" /></div>
              ) : view.todays.length === 0 && view.overdue.length === 0 ? (
                <p className="px-3 py-6 text-center text-sm text-slate-500">
                  Nothing scheduled today. Enjoy the break, or add an event in the calendar. ☕
                </p>
              ) : (
                <div>
                  {view.overdue.length > 0 && (
                    <div className="mb-2 rounded-xl bg-amber-50/60 p-1">
                      <div className="flex items-center justify-between px-3 pt-2">
                        <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">
                          Catch up
                        </p>
                        <RescheduleButton
                          spaceIds={view.overdueSpaceIds}
                          onResult={setCatchupNote}
                          onDone={() => {
                            void loadItems()
                            void reload()
                          }}
                        />
                      </div>
                      {view.overdue.map((i) => (
                        <CalendarRow key={i.id} item={i} onToggle={toggle} showDate />
                      ))}
                      {catchupNote && (
                        <p className="px-3 pb-2 text-xs text-emerald-700">{catchupNote}</p>
                      )}
                    </div>
                  )}
                  {view.todays.map((i) => (
                    <CalendarRow key={i.id} item={i} onToggle={toggle} />
                  ))}
                </div>
              )}
            </Card>

            <div className="space-y-6 lg:col-span-2">
              <Card className="p-4">
                <h2 className="mb-2 px-1 font-semibold text-slate-900">Exam countdown</h2>
                {view.exams.length === 0 ? (
                  <p className="px-1 py-3 text-sm text-slate-500">
                    No exams yet. Set a date in a subject chat or import your calendar.
                  </p>
                ) : (
                  <ul className="space-y-1">
                    {view.exams.map((e) => (
                      <li key={e.id} className="flex items-center justify-between gap-2 rounded-xl px-2 py-2">
                        <div className="min-w-0">
                          <p className="truncate text-sm font-medium text-slate-800">{e.title}</p>
                          <p className="text-xs text-slate-500">{formatLong(e.date)}</p>
                        </div>
                        <Countdown date={e.date} />
                      </li>
                    ))}
                  </ul>
                )}
              </Card>

              <Card className="p-4">
                <h2 className="mb-2 px-1 font-semibold text-slate-900">Coming up</h2>
                {view.upcoming.length === 0 ? (
                  <p className="px-1 py-3 text-sm text-slate-500">A quiet week ahead.</p>
                ) : (
                  view.upcoming.map((i) => (
                    <CalendarRow key={i.id} item={i} onToggle={toggle} showDate showSpace={false} />
                  ))
                )}
              </Card>
            </div>
          </div>

          <div>
            <h2 className="mb-3 font-semibold text-slate-900">Your subjects</h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {spaces.map((s) => {
                const color = spaceColor(s.id)
                const status = STATUS[s.status]
                return (
                  <Card key={s.id} className="group relative overflow-hidden transition hover:-translate-y-0.5 hover:shadow-md">
                    <div className={`h-1.5 bg-gradient-to-r ${color.bar}`} />
                    <Link to={`/spaces/${s.id}`} className="block p-4">
                      <div className="mb-3 flex items-start justify-between gap-2">
                        <h3 className="font-semibold text-slate-900">{s.name}</h3>
                        <Badge className={status.tone}>{status.label}</Badge>
                      </div>
                      <div className="mb-3 flex flex-wrap gap-1.5">
                        {s.exam_date ? <Countdown date={s.exam_date} /> : (
                          <Badge>No exam date</Badge>
                        )}
                      </div>
                      {s.sessions_total > 0 ? (
                        <>
                          <ProgressBar value={s.sessions_done} max={s.sessions_total} gradient={color.bar} />
                          <p className="mt-1.5 text-xs text-slate-500">
                            {s.sessions_done}/{s.sessions_total} sessions done ·{' '}
                            {s.source_count} source{s.source_count === 1 ? '' : 's'}
                          </p>
                        </>
                      ) : (
                        <p className="text-xs text-slate-500">
                          {s.source_count} source{s.source_count === 1 ? '' : 's'} ·{' '}
                          {s.status === 'ready' ? 'no plan yet' : 'chat to build your plan'}
                        </p>
                      )}
                    </Link>
                    <button
                      onClick={() => removeSpace(s.id, s.name)}
                      title="Delete subject"
                      aria-label={`Delete ${s.name}`}
                      className="absolute right-3 top-5 hidden rounded-lg p-1 text-slate-300 hover:bg-rose-50 hover:text-rose-600 group-hover:block"
                    >
                      ✕
                    </button>
                  </Card>
                )
              })}
              <button
                onClick={onNewSpace}
                className="flex min-h-[9rem] items-center justify-center rounded-2xl border-2 border-dashed border-slate-300 text-sm font-medium text-slate-500 transition hover:border-indigo-300 hover:bg-white hover:text-indigo-600"
              >
                + New subject
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  )
}
