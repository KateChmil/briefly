import type { CalendarItem } from '../types'
import { formatMinutes, formatShort } from '../lib/dates'
import { kindStyle, spaceColor } from '../lib/theme'
import { Badge } from './ui'

interface Props {
  item: CalendarItem
  onToggle?: (item: CalendarItem, done: boolean) => void
  onDelete?: (item: CalendarItem) => void
  showDate?: boolean
  showSpace?: boolean
}

export function sessionIdOf(item: CalendarItem): number {
  return Number(item.id.split('-')[1])
}

/** One line of the agenda: a checkable study session, or an event/exam. */
export default function CalendarRow({
  item,
  onToggle,
  onDelete,
  showDate = false,
  showSpace = true,
}: Props) {
  const style = kindStyle(item.kind)
  const isSession = item.type === 'session'
  const time = item.start_time
    ? item.end_time
      ? `${item.start_time}–${item.end_time}`
      : item.start_time
    : null

  return (
    <div
      className={`group flex items-start gap-3 rounded-xl px-3 py-2.5 transition hover:bg-slate-50 ${
        item.done ? 'opacity-60' : ''
      }`}
    >
      {isSession ? (
        <button
          role="checkbox"
          aria-checked={!!item.done}
          aria-label={`Mark "${item.title}" ${item.done ? 'not done' : 'done'}`}
          onClick={() => onToggle?.(item, !item.done)}
          disabled={!onToggle}
          className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border-2 text-xs font-bold transition ${
            item.done
              ? 'border-emerald-500 bg-emerald-500 text-white'
              : 'border-slate-300 bg-white text-transparent hover:border-emerald-400'
          }`}
        >
          ✓
        </button>
      ) : (
        <span className={`mt-1.5 h-2.5 w-2.5 shrink-0 rounded-full ${style.dot}`} />
      )}

      <div className="min-w-0 flex-1">
        <p
          className={`text-sm font-medium text-slate-800 ${
            item.done ? 'line-through' : ''
          }`}
        >
          {item.title}
        </p>
        <div className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-slate-500">
          {showDate && <span>{formatShort(item.date)}</span>}
          {time && <span>{time}</span>}
          {isSession && item.minutes ? <span>{formatMinutes(item.minutes)}</span> : null}
          {item.topic && <span className="truncate">{item.topic}</span>}
        </div>
      </div>

      <div className="flex shrink-0 flex-col items-end gap-1">
        <Badge className={style.chip}>{style.label}</Badge>
        {showSpace && item.space_name && (
          <span
            className={`max-w-[9rem] truncate rounded-full px-2 py-0.5 text-[11px] font-medium ${
              spaceColor(item.space_id).soft
            }`}
          >
            {item.space_name}
          </span>
        )}
      </div>

      {item.deletable && onDelete && (
        <button
          onClick={() => onDelete(item)}
          aria-label={`Delete ${item.title}`}
          title="Delete event"
          className="mt-0.5 hidden rounded p-0.5 text-slate-300 hover:bg-rose-50 hover:text-rose-600 group-hover:block"
        >
          ✕
        </button>
      )}
    </div>
  )
}
