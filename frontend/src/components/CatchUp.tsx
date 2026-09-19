import { useState } from 'react'
import { api } from '../api/client'
import type { RescheduleResult } from '../types'
import { Button } from './ui'

export function summarize(res: RescheduleResult): string {
  const moved = `Moved ${res.moved} session${res.moved === 1 ? '' : 's'}`
  return res.unplaced.length
    ? `${moved}, ${res.unplaced.length} didn't fit before your exam`
    : moved
}

/** Amber banner shown in the plan when sessions slipped past their date. */
export function CatchUpBanner({
  spaceId,
  overdue,
  onRescheduled,
}: {
  spaceId: string
  overdue: number
  onRescheduled: (result: RescheduleResult) => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const run = async () => {
    setBusy(true)
    setError('')
    try {
      onRescheduled(await api.rescheduleSessions(spaceId))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Reschedule failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex flex-wrap items-center justify-between gap-2 rounded-2xl bg-amber-50 p-3 ring-1 ring-amber-200">
      <p className="text-sm font-medium text-amber-800">
        ⚠️ You're {overdue} session{overdue === 1 ? '' : 's'} behind
      </p>
      <div className="flex items-center gap-2">
        {error && <span className="text-xs text-rose-600">{error}</span>}
        <Button size="sm" onClick={() => void run()} disabled={busy}>
          {busy ? 'Rescheduling…' : 'Reschedule for me'}
        </Button>
      </div>
    </div>
  )
}

/** Compact "Reschedule" button that can catch up several subjects at once. */
export function RescheduleButton({
  spaceIds,
  onDone,
  onResult,
}: {
  spaceIds: string[]
  onDone?: () => void
  onResult?: (summary: string) => void
}) {
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  const run = async () => {
    setBusy(true)
    setError('')
    try {
      const results = await Promise.all(
        spaceIds.map((id) => api.rescheduleSessions(id)),
      )
      const moved = results.reduce((n, r) => n + r.moved, 0)
      const unplaced = results.reduce((n, r) => n + r.unplaced.length, 0)
      onResult?.(
        unplaced
          ? `Moved ${moved} session${moved === 1 ? '' : 's'}, ${unplaced} didn't fit before the exam`
          : `Moved ${moved} session${moved === 1 ? '' : 's'}`,
      )
      onDone?.()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Reschedule failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <span className="inline-flex items-center gap-2">
      <Button
        size="sm"
        variant="secondary"
        disabled={busy || spaceIds.length === 0}
        onClick={() => void run()}
      >
        {busy ? 'Rescheduling…' : '↻ Reschedule'}
      </Button>
      {error && <span className="text-xs text-rose-600">{error}</span>}
    </span>
  )
}
