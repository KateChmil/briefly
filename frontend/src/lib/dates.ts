// All dates are handled as local calendar days ("YYYY-MM-DD"), never as UTC
// instants, so an exam on the 30th never slides to the 29th or 31st.

export function toISO(d: Date): string {
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${d.getFullYear()}-${m}-${day}`
}

export function parseISO(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split('-').map(Number)
  return new Date(y, (m || 1) - 1, d || 1)
}

export const todayISO = () => toISO(new Date())

export function addDays(iso: string, n: number): string {
  const d = parseISO(iso)
  d.setDate(d.getDate() + n)
  return toISO(d)
}

/** Whole days from today until `iso` (negative if in the past). */
export function daysUntil(iso: string, from: string = todayISO()): number {
  const ms = parseISO(iso).getTime() - parseISO(from).getTime()
  return Math.round(ms / 86_400_000)
}

export function countdownLabel(days: number): string {
  if (days === 0) return 'Today'
  if (days === 1) return 'Tomorrow'
  if (days === -1) return 'Yesterday'
  return days > 0 ? `in ${days} days` : `${-days} days ago`
}

/** Monday of the week containing `iso`. */
export function weekStart(iso: string): string {
  const d = parseISO(iso)
  const offset = (d.getDay() + 6) % 7 // Monday = 0
  d.setDate(d.getDate() - offset)
  return toISO(d)
}

/** The 6x7 grid of days (Monday first) that covers a month. */
export function monthGrid(year: number, month: number): string[] {
  const first = toISO(new Date(year, month, 1))
  const start = weekStart(first)
  return Array.from({ length: 42 }, (_, i) => addDays(start, i))
}

const fmt = (opts: Intl.DateTimeFormatOptions) => (iso: string) =>
  parseISO(iso).toLocaleDateString(undefined, opts)

export const formatShort = fmt({ month: 'short', day: 'numeric' })
export const formatWeekday = fmt({ weekday: 'short' })
export const formatLong = fmt({ weekday: 'long', month: 'long', day: 'numeric' })
export const formatMonth = (year: number, month: number) =>
  new Date(year, month, 1).toLocaleDateString(undefined, {
    month: 'long',
    year: 'numeric',
  })

export function greeting(now: Date = new Date()): string {
  const h = now.getHours()
  if (h < 5) return 'Burning the midnight oil'
  if (h < 12) return 'Good morning'
  if (h < 18) return 'Good afternoon'
  return 'Good evening'
}

export function formatMinutes(min: number): string {
  if (min < 60) return `${min} min`
  const h = Math.floor(min / 60)
  const r = min % 60
  return r ? `${h}h ${r}m` : `${h}h`
}
