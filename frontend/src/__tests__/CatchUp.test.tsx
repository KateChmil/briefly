import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'

vi.mock('../api/client', () => ({
  api: { rescheduleSessions: vi.fn() },
}))

import { api } from '../api/client'
import { CatchUpBanner, RescheduleButton, summarize } from '../components/CatchUp'
import type { StudySession } from '../types'

beforeEach(() => vi.clearAllMocks())

const session = (id: number): StudySession => ({
  id,
  space_id: 's',
  date: '2026-03-11',
  title: `s${id}`,
  topic: '',
  minutes: 45,
  kind: 'study',
  done: false,
})

describe('CatchUpBanner', () => {
  it('shows the overdue count and reschedules on click', async () => {
    vi.mocked(api.rescheduleSessions).mockResolvedValue({
      sessions: [session(1)],
      moved: 1,
      unplaced: [],
    })
    const onRescheduled = vi.fn()
    render(<CatchUpBanner spaceId="s1" overdue={2} onRescheduled={onRescheduled} />)
    expect(screen.getByText(/2 sessions behind/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: /Reschedule for me/ }))
    await waitFor(() => expect(onRescheduled).toHaveBeenCalled())
    expect(api.rescheduleSessions).toHaveBeenCalledWith('s1')
  })

  it('shows a friendly message when the call fails', async () => {
    vi.mocked(api.rescheduleSessions).mockRejectedValue(new Error('boom'))
    render(<CatchUpBanner spaceId="s1" overdue={1} onRescheduled={() => {}} />)
    fireEvent.click(screen.getByRole('button', { name: /Reschedule for me/ }))
    await waitFor(() => expect(screen.getByText('boom')).toBeInTheDocument())
  })
})

describe('RescheduleButton', () => {
  it('reschedules every subject with overdue sessions', async () => {
    vi.mocked(api.rescheduleSessions).mockResolvedValue({
      sessions: [],
      moved: 1,
      unplaced: [session(9)],
    })
    const onResult = vi.fn()
    const onDone = vi.fn()
    render(
      <RescheduleButton spaceIds={['a', 'b']} onResult={onResult} onDone={onDone} />,
    )
    fireEvent.click(screen.getByRole('button', { name: /Reschedule/ }))
    await waitFor(() => expect(onDone).toHaveBeenCalled())
    expect(api.rescheduleSessions).toHaveBeenCalledTimes(2)
    expect(onResult).toHaveBeenCalledWith(
      "Moved 2 sessions, 2 didn't fit before the exam",
    )
  })
})

describe('summarize', () => {
  it('mentions only the moved count when everything fit', () => {
    expect(summarize({ sessions: [], moved: 3, unplaced: [] })).toBe(
      'Moved 3 sessions',
    )
  })

  it('reports sessions that did not fit', () => {
    expect(
      summarize({ sessions: [], moved: 3, unplaced: [session(1)] }),
    ).toBe("Moved 3 sessions, 1 didn't fit before your exam")
  })
})
