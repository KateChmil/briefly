import type { ButtonHTMLAttributes, ReactNode } from 'react'

export function Button({
  variant = 'primary',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: 'primary' | 'ghost' | 'danger'
}) {
  const styles = {
    primary:
      'bg-indigo-600 text-white hover:bg-indigo-500 disabled:bg-indigo-300',
    ghost:
      'bg-transparent text-slate-600 hover:bg-slate-100 border border-slate-300',
    danger: 'bg-transparent text-red-600 hover:bg-red-50',
  }[variant]
  return (
    <button
      className={`rounded-lg px-3 py-1.5 text-sm font-medium transition-colors disabled:cursor-not-allowed ${styles} ${className}`}
      {...props}
    />
  )
}

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-slate-500 text-sm">
      <div className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600" />
      {label && <span>{label}</span>}
    </div>
  )
}

export function Badge({ children }: { children: ReactNode }) {
  return (
    <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600">
      {children}
    </span>
  )
}
