import { useCallback, useEffect, useMemo, useState } from 'react'
import { api } from '../api/client'
import AddEventModal from '../components/AddEventModal'
import CalendarRow, { sessionIdOf } from '../components/CalendarRow'
import ImportCalendarModal from '../components/ImportCalendarModal'
import { Button, Card, ErrorNote } from '../components/ui'
import {
  countdownLabel,
  daysUntil,
  formatLong,
  formatMonth,
  monthGrid,
  parseISO,
  todayISO,
} from '../lib/dates'
import { useSpaces } from '../lib/spaces'
import { KIND_STYLE, kindStyle } from '../lib/theme'
import type { CalendarItem } from '../types'

const WEEKDAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
const MAX_CHIPS = 3

export default function CalendarPage() {
  const today = todayISO()
  const now = new Date()
  const [cursor, setCursor] = useState({ year: now.getFullYear(), month: now.getMonth() })
  const [selected, setSelected] = useState(today)
  const [items, setItems] = useState<CalendarItem[]>([])
  const [spaceFilter, setSpaceFilter] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [addOpen, setAddOpen] = useState(false)
  const [importOpen, setImportOpen] = useState(false)
  const { spaces, reload } = useSpaces()

  const grid = useMemo(() => monthGrid(cursor.year, cursor.month), [cursor])

  const load = useCallback(async () => {
    try {
      setItems(await api.getCalendar(grid[0], grid[41], spaceFilter || undefined))
      setError('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load the calendar')
    } finally {
      setLoading(false)
    }
  }, [grid, spaceFilter])

  useEffect(() => {
    void load()
  }, [load])

  const byDay = useMemo(() => {
    const map = new Map<string, CalendarItem[]>()
    for (const i of items) map.set(i.date, [...(map.get(i.date) ?? []), i])
    return map
  }, [items])

  const move = (delta: number) =>
    setCursor(({ year, month }) => {
      const d = new Date(year, month + delta, 1)
      return { year: d.getFullYear(), month: d.getMonth() }
    })

  const goToday = () => {
    setCursor({ year: now.getFullYear(), month: now.getMonth() })
    setSelected(today)
  }

  const toggle = async (item: CalendarItem, done: boolean) => {
    setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, done } : i)))
    try {
      await api.setSessionDone(sessionIdOf(item), done)
      void reload()
    } catch (e) {
      setItems((prev) => prev.map((i) => (i.id === item.id ? { ...i, done: !done } : i)))
      setError(e instanceof Error ? e.message : 'Could not update the session')
    }
  }

  const remove = async (item: CalendarItem) => {
    try {
      await api.deleteEvent(item.id)
      await load()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Could not delete the event')
    }
  }

  const dayItems = byDay.get(selected) ?? []
  const nextExam = items.find((i) => i.kind === 'exam' && i.date >= today)

  return (
    <div className="mx-auto max-w-7xl px-4 py-6 sm:px-8 sm:py-8">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">Calendar</h1>
          <p className="text-sm text-slate-500">
            Classes, exams and your study plan in one place.
            {nextExam && (
              <>
                {' '}Next exam: <b>{nextExam.title}</b> {countdownLabel(daysUntil(nextExam.date))}.
              </>
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <select
            value={spaceFilter}
            onChange={(e) => setSpaceFilter(e.target.value)}
            aria-label="Filter by subject"
            className="rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 outline-none focus:border-indigo-400"
          >
            <option value="">All subjects</option>
            {spaces?.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          <Button variant="secondary" onClick={() => setImportOpen(true)}>
            ⬇ Import
          </Button>
          <a
            href={api.exportUrl(spaceFilter || undefined)}
            className="inline-flex items-center rounded-xl bg-white px-3.5 py-2 text-sm font-medium text-slate-700 ring-1 ring-slate-200 transition hover:bg-slate-50"
          >
            ⬆ Export .ics
          </a>
          <Button onClick={() => setAddOpen(true)}>+ Add event</Button>
        </div>
      </div>

      {error && <div className="mb-4"><ErrorNote>{error}</ErrorNote></div>}

      <div className="grid gap-6 lg:grid-cols-[1fr_22rem]">
        <Card className="p-3 sm:p-4">
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-900">
              {formatMonth(cursor.year, cursor.month)}
            </h2>
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="sm" onClick={() => move(-1)} aria-label="Previous month">
                ‹
              </Button>
              <Button variant="secondary" size="sm" onClick={goToday}>
                Today
              </Button>
              <Button variant="ghost" size="sm" onClick={() => move(1)} aria-label="Next month">
                ›
              </Button>
            </div>
          </div>

          <div className="grid grid-cols-7 gap-px overflow-hidden rounded-xl bg-slate-200 ring-1 ring-slate-200">
            {WEEKDAYS.map((d) => (
              <div key={d} className="bg-slate-50 py-1.5 text-center text-xs font-semibold text-slate-500">
                {d}
              </div>
            ))}
            {grid.map((iso) => {
              const inMonth = parseISO(iso).getMonth() === cursor.month
              const list = byDay.get(iso) ?? []
              const isToday = iso === today
              const isSelected = iso === selected
              return (
                <button
                  key={iso}
                  onClick={() => setSelected(iso)}
                  aria-label={`${formatLong(iso)}, ${list.length} item${list.length === 1 ? '' : 's'}`}
                  aria-pressed={isSelected}
                  className={`flex min-h-[4.5rem] flex-col gap-0.5 p-1 text-left align-top transition sm:min-h-[6.5rem] sm:p-1.5 ${
                    inMonth ? 'bg-white' : 'bg-slate-50/70'
                  } ${isSelected ? 'relative z-10 ring-2 ring-inset ring-indigo-500' : 'hover:bg-indigo-50/40'}`}
                >
                  <span
                    className={`flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium ${
                      isToday
                        ? 'bg-indigo-600 text-white'
                        : inMonth
                          ? 'text-slate-700'
                          : 'text-slate-400'
                    }`}
                  >
                    {parseISO(iso).getDate()}
                  </span>
                  {/* on phones show dots; on wider screens show titles */}
                  <div className="flex flex-wrap gap-0.5 sm:hidden">
                    {list.slice(0, 6).map((i) => (
                      <span key={i.id} className={`h-1.5 w-1.5 rounded-full ${kindStyle(i.kind).dot}`} />
                    ))}
                  </div>
                  <div className="hidden min-w-0 flex-col gap-0.5 sm:flex">
                    {list.slice(0, MAX_CHIPS).map((i) => (
                      <span
                        key={i.id}
                        className={`truncate rounded px-1 py-0.5 text-[11px] font-medium leading-tight ring-1 ring-inset ${
                          kindStyle(i.kind).chip
                        } ${i.done ? 'line-through opacity-60' : ''}`}
                      >
                        {i.type === 'exam' ? '🎯 ' : ''}
                        {i.title}
                      </span>
                    ))}
                    {list.length > MAX_CHIPS && (
                      <span className="px-1 text-[11px] text-slate-500">
                        +{list.length - MAX_CHIPS} more
                      </span>
                    )}
                  </div>
                </button>
              )
            })}
          </div>

          <div className="mt-3 flex flex-wrap gap-x-4 gap-y-1 px-1 text-xs text-slate-500">
            {Object.entries(KIND_STYLE).map(([key, s]) => (
              <span key={key} className="inline-flex items-center gap-1.5">
                <span className={`h-2 w-2 rounded-full ${s.dot}`} />
                {s.label}
              </span>
            ))}
          </div>
        </Card>

        <Card className="h-fit p-4 lg:sticky lg:top-6">
          <div className="mb-2 flex items-center justify-between px-1">
            <div>
              <h2 className="font-semibold text-slate-900">{formatLong(selected)}</h2>
              <p className="text-xs text-slate-500">{countdownLabel(daysUntil(selected))}</p>
            </div>
            <Button size="sm" variant="secondary" onClick={() => setAddOpen(true)}>
              + Add
            </Button>
          </div>
          {loading ? (
            <p className="px-2 py-6 text-center text-sm text-slate-400">Loading…</p>
          ) : dayItems.length === 0 ? (
            <p className="px-2 py-8 text-center text-sm text-slate-500">
              Nothing on this day. 🌤️
            </p>
          ) : (
            dayItems.map((i) => (
              <CalendarRow key={i.id} item={i} onToggle={toggle} onDelete={remove} />
            ))
          )}
        </Card>
      </div>

      {addOpen && (
        <AddEventModal
          initialDate={selected}
          onClose={() => setAddOpen(false)}
          onSaved={() => {
            setAddOpen(false)
            void load()
          }}
        />
      )}
      {importOpen && (
        <ImportCalendarModal onClose={() => setImportOpen(false)} onImported={() => void load()} />
      )}
    </div>
  )
}
