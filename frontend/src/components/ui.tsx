import { Component, useEffect } from 'react'
import type {
  ButtonHTMLAttributes,
  ErrorInfo,
  ReactNode,
} from 'react'
import { daysUntil } from '../lib/dates'

export function Button({
  variant = 'primary',
  size = 'md',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md'
}) {
  const styles = {
    primary:
      'bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-sm hover:from-indigo-500 hover:to-violet-500 disabled:from-indigo-300 disabled:to-violet-300',
    secondary:
      'bg-white text-slate-700 ring-1 ring-slate-200 hover:bg-slate-50 hover:ring-slate-300 disabled:text-slate-400',
    ghost: 'bg-transparent text-slate-600 hover:bg-slate-100 disabled:text-slate-400',
    danger: 'bg-transparent text-rose-600 hover:bg-rose-50',
  }[variant]
  const sizes = { sm: 'px-2.5 py-1 text-xs', md: 'px-3.5 py-2 text-sm' }[size]
  return (
    <button
      className={`inline-flex items-center justify-center gap-1.5 rounded-xl font-medium transition-all focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400 active:scale-[0.98] disabled:cursor-not-allowed disabled:active:scale-100 ${sizes} ${styles} ${className}`}
      {...props}
    />
  )
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-500">
      <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-200 border-t-indigo-600" />
      {label && <span>{label}</span>}
    </div>
  )
}

export function Badge({
  children,
  className = 'bg-slate-100 text-slate-600 ring-slate-200',
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset ${className}`}
    >
      {children}
    </span>
  )
}

export function Card({
  children,
  className = '',
}: {
  children: ReactNode
  className?: string
}) {
  return (
    <div
      className={`rounded-2xl bg-white shadow-sm ring-1 ring-slate-200/70 ${className}`}
    >
      {children}
    </div>
  )
}

export function ProgressBar({
  value,
  max,
  gradient = 'from-indigo-500 to-violet-500',
  className = '',
}: {
  value: number
  max: number
  gradient?: string
  className?: string
}) {
  const pct = max > 0 ? Math.min(100, Math.round((value / max) * 100)) : 0
  return (
    <div
      className={`h-2 overflow-hidden rounded-full bg-slate-100 ${className}`}
      role="progressbar"
      aria-valuenow={pct}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      <div
        className={`h-full rounded-full bg-gradient-to-r ${gradient} transition-all duration-500`}
        style={{ width: `${pct}%` }}
      />
    </div>
  )
}

export function EmptyState({
  icon,
  title,
  children,
}: {
  icon: string
  title: string
  children?: ReactNode
}) {
  return (
    <div className="flex flex-col items-center rounded-2xl border border-dashed border-slate-300 bg-white/60 px-6 py-10 text-center">
      <div className="mb-3 text-4xl">{icon}</div>
      <p className="font-semibold text-slate-800">{title}</p>
      {children && <div className="mt-1 max-w-sm text-sm text-slate-500">{children}</div>}
    </div>
  )
}

export function Modal({
  title,
  onClose,
  children,
  width = 'max-w-md',
}: {
  title: string
  onClose: () => void
  children: ReactNode
  width?: string
}) {
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  return (
    <div
      className="animate-fade-in fixed inset-0 z-40 flex items-end justify-center bg-slate-900/40 p-0 backdrop-blur-sm sm:items-center sm:p-4"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={title}
        className={`animate-pop-in flex max-h-[90vh] w-full flex-col rounded-t-3xl bg-white shadow-2xl sm:rounded-2xl ${width}`}
      >
        <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
          <h2 className="text-base font-semibold text-slate-900">{title}</h2>
          <button
            onClick={onClose}
            aria-label="Close"
            className="rounded-lg p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600"
          >
            ✕
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">{children}</div>
      </div>
    </div>
  )
}

export const inputClass =
  'w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100'

export function Field({
  label,
  children,
}: {
  label: string
  children: ReactNode
}) {
  return (
    <label className="block">
      <span className="mb-1 block text-xs font-medium text-slate-600">{label}</span>
      {children}
    </label>
  )
}

/** "in 12 days" chip, coloured by urgency. */
export function Countdown({ date }: { date: string }) {
  const days = daysUntil(date)
  const tone =
    days < 0
      ? 'bg-slate-100 text-slate-500 ring-slate-200'
      : days <= 3
        ? 'bg-rose-50 text-rose-700 ring-rose-200'
        : days <= 14
          ? 'bg-amber-50 text-amber-700 ring-amber-200'
          : 'bg-emerald-50 text-emerald-700 ring-emerald-200'
  const text =
    days === 0 ? 'Exam today' : days === 1 ? 'Exam tomorrow' : days < 0 ? 'Exam passed' : `Exam in ${days}d`
  return <Badge className={tone}>🎯 {text}</Badge>
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return (
    <div
      role="alert"
      className="rounded-xl bg-rose-50 px-3 py-2 text-sm text-rose-700 ring-1 ring-rose-200"
    >
      {children}
    </div>
  )
}

interface BoundaryState {
  error: Error | null
}

/** Keeps one broken component from blanking the whole app. */
export class ErrorBoundary extends Component<{ children: ReactNode }, BoundaryState> {
  state: BoundaryState = { error: null }

  static getDerivedStateFromError(error: Error): BoundaryState {
    return { error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('UI error:', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div className="mx-auto max-w-md p-10 text-center">
        <div className="mb-3 text-4xl">😵</div>
        <h1 className="mb-1 text-lg font-semibold text-slate-900">Something went wrong</h1>
        <p className="mb-4 text-sm text-slate-500">{this.state.error.message}</p>
        <Button onClick={() => this.setState({ error: null })}>Try again</Button>
      </div>
    )
  }
}
