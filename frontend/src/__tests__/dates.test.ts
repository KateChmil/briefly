import { describe, expect, it } from 'vitest'
import {
  addDays,
  countdownLabel,
  daysUntil,
  formatMinutes,
  monthGrid,
  parseISO,
  toISO,
  weekStart,
} from '../lib/dates'

describe('dates', () => {
  it('round-trips ISO days without timezone drift', () => {
    expect(toISO(parseISO('2026-10-30'))).toBe('2026-10-30')
    expect(parseISO('2026-10-30').getDate()).toBe(30)
  })

  it('adds days across month and year ends', () => {
    expect(addDays('2026-01-31', 1)).toBe('2026-02-01')
    expect(addDays('2026-12-31', 1)).toBe('2027-01-01')
    expect(addDays('2026-03-01', -1)).toBe('2026-02-28')
  })

  it('counts whole days even across daylight-saving changes', () => {
    expect(daysUntil('2026-03-30', '2026-03-28')).toBe(2)
    expect(daysUntil('2026-11-02', '2026-10-30')).toBe(3)
    expect(daysUntil('2026-10-01', '2026-10-05')).toBe(-4)
  })

  it('labels countdowns', () => {
    expect(countdownLabel(0)).toBe('Today')
    expect(countdownLabel(1)).toBe('Tomorrow')
    expect(countdownLabel(12)).toBe('in 12 days')
    expect(countdownLabel(-3)).toBe('3 days ago')
  })

  it('starts weeks on Monday', () => {
    expect(weekStart('2026-09-19')).toBe('2026-09-14') // Saturday
    expect(weekStart('2026-09-14')).toBe('2026-09-14') // Monday
    expect(weekStart('2026-09-20')).toBe('2026-09-14') // Sunday
  })

  it('builds a 6-week Monday-first month grid that contains the month', () => {
    const grid = monthGrid(2026, 8) // September 2026
    expect(grid).toHaveLength(42)
    expect(parseISO(grid[0]).getDay()).toBe(1) // Monday
    expect(grid).toContain('2026-09-01')
    expect(grid).toContain('2026-09-30')
  })

  it('formats minutes', () => {
    expect(formatMinutes(45)).toBe('45 min')
    expect(formatMinutes(60)).toBe('1h')
    expect(formatMinutes(90)).toBe('1h 30m')
  })
})
