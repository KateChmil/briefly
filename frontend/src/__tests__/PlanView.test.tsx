import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import PlanView from '../components/PlanView'
import { addDays, todayISO } from '../lib/dates'
import type { StudySession } from '../types'

const today = todayISO()
const sessions: StudySession[] = [
  { id: 1, space_id: 's', date: addDays(today, 1), title: 'Cells basics', topic: 'cells.txt', minutes: 45, kind: 'study', done: false },
  { id: 2, space_id: 's', date: addDays(today, 2), title: 'Genetics review', topic: '', minutes: 90, kind: 'review', done: true },
]
const content = JSON.stringify({
  overview: '## Plan\nStudy daily.',
  sessions: sessions.map(({ date, title, topic, minutes, kind }) => ({ date, title, topic, minutes, kind })),
})

describe('PlanView', () => {
  it('shows progress, strategy and sessions', () => {
    render(<PlanView spaceId="s" content={content} sessions={sessions} onToggle={() => {}} />)
    expect(screen.getByText('1/2 sessions done')).toBeInTheDocument()
    expect(screen.getByText('Study daily.')).toBeInTheDocument()
    // once in the "Up next" line and once in the session list
    expect(screen.getAllByText('Cells basics')).toHaveLength(2)
    expect(screen.getByText(/Up next:/)).toBeInTheDocument()
  })

  it('reports toggles to the parent', () => {
    const onToggle = vi.fn()
    render(<PlanView spaceId="s" content={content} sessions={sessions} onToggle={onToggle} />)
    fireEvent.click(screen.getByRole('checkbox', { name: /Cells basics/ }))
    expect(onToggle).toHaveBeenCalledWith(sessions[0], true)
    fireEvent.click(screen.getByRole('checkbox', { name: /Genetics review/ }))
    expect(onToggle).toHaveBeenCalledWith(sessions[1], false)
  })

  it('falls back to Markdown for plans generated before structured output', () => {
    render(<PlanView spaceId="s" content={'# Old plan\n\n- read chapter 1'} sessions={[]} onToggle={() => {}} />)
    expect(screen.getByText('Old plan')).toBeInTheDocument()
    expect(screen.getByText('read chapter 1')).toBeInTheDocument()
  })
})
