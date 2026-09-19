import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import CanvasPicker from '../components/CanvasPicker'

vi.mock('../api/client', () => ({
  api: {
    getCanvasStatus: vi.fn(() => Promise.resolve({ mode: 'mock' })),
    listCanvasCourses: vi.fn(() =>
      Promise.resolve([
        { id: 'bio', name: 'Biology 101' },
        { id: 'calc', name: 'Calculus II' },
      ]),
    ),
    listCanvasFiles: vi.fn(() =>
      Promise.resolve([
        { id: 'bio/files/notes.txt', name: 'notes.txt' },
        { id: 'bio/files/lab.txt', name: 'lab.txt' },
      ]),
    ),
    importCanvasFiles: vi.fn(() =>
      Promise.resolve({ imported: [{ id: 'x' }], skipped: [] }),
    ),
    importCanvasAssignments: vi.fn(() =>
      Promise.resolve({ imported: 3, skipped: 1 }),
    ),
  },
}))

describe('CanvasPicker', () => {
  it('browses courses and imports selected files', async () => {
    const onImported = vi.fn(() => Promise.resolve())
    render(
      <CanvasPicker spaceId="s1" onClose={() => {}} onImported={onImported} />,
    )

    expect(await screen.findByText(/Demo data/)).toBeInTheDocument()
    fireEvent.click(await screen.findByRole('button', { name: 'Biology 101' }))
    fireEvent.click(await screen.findByLabelText('notes.txt'))
    fireEvent.click(screen.getByRole('button', { name: 'Import 1 file' }))

    await waitFor(() =>
      expect(api.importCanvasFiles).toHaveBeenCalledWith('s1', [
        'bio/files/notes.txt',
      ]),
    )
    await waitFor(() => expect(onImported).toHaveBeenCalled())
  })

  it('adds assignment due dates to the calendar', async () => {
    render(
      <CanvasPicker
        spaceId="s1"
        onClose={() => {}}
        onImported={() => Promise.resolve()}
      />,
    )
    const buttons = await screen.findAllByRole('button', { name: /Due dates/ })
    fireEvent.click(buttons[0])
    await waitFor(() =>
      expect(api.importCanvasAssignments).toHaveBeenCalledWith('s1', 'bio'),
    )
    expect(await screen.findByText(/Added 3 due dates/)).toBeInTheDocument()
  })
})
