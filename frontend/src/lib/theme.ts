// Tailwind only generates classes it can see as complete strings, so every
// colour variant is spelled out here instead of being built dynamically.

export interface KindStyle {
  label: string
  dot: string
  chip: string
}

const style = (label: string, dot: string, chip: string): KindStyle => ({
  label,
  dot,
  chip,
})

export const KIND_STYLE: Record<string, KindStyle> = {
  exam: style('Exam', 'bg-rose-500', 'bg-rose-50 text-rose-700 ring-rose-200'),
  class: style('Class', 'bg-sky-500', 'bg-sky-50 text-sky-700 ring-sky-200'),
  other: style('Event', 'bg-slate-400', 'bg-slate-100 text-slate-600 ring-slate-200'),
  study: style('Study', 'bg-emerald-500', 'bg-emerald-50 text-emerald-700 ring-emerald-200'),
  review: style('Review', 'bg-amber-500', 'bg-amber-50 text-amber-700 ring-amber-200'),
  practice: style('Practice', 'bg-violet-500', 'bg-violet-50 text-violet-700 ring-violet-200'),
  mock_exam: style('Mock exam', 'bg-fuchsia-500', 'bg-fuchsia-50 text-fuchsia-700 ring-fuchsia-200'),
}

export const kindStyle = (kind: string): KindStyle =>
  KIND_STYLE[kind] ?? KIND_STYLE.other

export interface SpaceColor {
  dot: string
  soft: string
  bar: string
}

const SPACE_COLORS: SpaceColor[] = [
  { dot: 'bg-indigo-500', soft: 'bg-indigo-50 text-indigo-700', bar: 'from-indigo-500 to-violet-500' },
  { dot: 'bg-emerald-500', soft: 'bg-emerald-50 text-emerald-700', bar: 'from-emerald-500 to-teal-500' },
  { dot: 'bg-rose-500', soft: 'bg-rose-50 text-rose-700', bar: 'from-rose-500 to-orange-400' },
  { dot: 'bg-amber-500', soft: 'bg-amber-50 text-amber-700', bar: 'from-amber-500 to-yellow-400' },
  { dot: 'bg-sky-500', soft: 'bg-sky-50 text-sky-700', bar: 'from-sky-500 to-cyan-400' },
  { dot: 'bg-fuchsia-500', soft: 'bg-fuchsia-50 text-fuchsia-700', bar: 'from-fuchsia-500 to-pink-400' },
]

/** A stable colour per space id, so a subject looks the same everywhere. */
export function spaceColor(id: string | null | undefined): SpaceColor {
  if (!id) return SPACE_COLORS[0]
  let h = 0
  for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) >>> 0
  return SPACE_COLORS[h % SPACE_COLORS.length]
}
