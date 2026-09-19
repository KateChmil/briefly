import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import MyNotes from '../components/MyNotes'

vi.mock('../api/client', () => ({
  api: {
    listUserNotes: vi.fn(),
    createUserNote: vi.fn(),
    updateUserNote: vi.fn(),
    deleteUserNote: vi.fn(),
    enhanceNote: vi.fn(),
  },
}))

import { api } from '../api/client'

const mocked = vi.mocked(api)

const note = (id: number, title: string, content = 'Cells have a nucleus.') => ({
  id,
  space_id: 's1',
  title,
  content,
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
})

beforeEach(() => {
  vi.clearAllMocks()
  mocked.listUserNotes.mockResolvedValue([note(1, 'Ch 1'), note(2, 'Ch 2')])
  mocked.updateUserNote.mockImplementation(async (id, patch) => ({
    ...note(id, patch.title ?? 'Ch 1', patch.content ?? ''),
  }))
})

describe('MyNotes', () => {
  it('lists notes and opens the first one for editing', async () => {
    render(<MyNotes spaceId="s1" />)
    expect(await screen.findByDisplayValue('Ch 1')).toBeInTheDocument()
    expect(screen.getByText('Ch 2')).toBeInTheDocument()
    expect(screen.getByLabelText('Note content')).toHaveValue(
      'Cells have a nucleus.',
    )
  })

  it('autosaves edits after a short debounce', async () => {
    render(<MyNotes spaceId="s1" />)
    const editor = await screen.findByLabelText('Note content')
    fireEvent.change(editor, { target: { value: 'new text' } })
    expect(screen.getByText('Saving…')).toBeInTheDocument()
    await waitFor(
      () =>
        expect(mocked.updateUserNote).toHaveBeenCalledWith(1, {
          title: 'Ch 1',
          content: 'new text',
        }),
      { timeout: 2500 },
    )
    expect(await screen.findByText('✓ Saved')).toBeInTheDocument()
  })

  it('creates a new note', async () => {
    mocked.createUserNote.mockResolvedValue(note(3, 'Untitled note', ''))
    render(<MyNotes spaceId="s1" />)
    await screen.findByDisplayValue('Ch 1')
    fireEvent.click(screen.getByText('+ New note'))
    await waitFor(() =>
      expect(mocked.createUserNote).toHaveBeenCalledWith('s1', {
        title: 'Untitled note',
        content: '',
      }),
    )
    expect(await screen.findByLabelText('Note content')).toHaveValue('')
  })

  it('enhances with AI and appends the result to the note', async () => {
    mocked.enhanceNote.mockResolvedValue({
      result: 'short summary',
      cards: null,
    })
    render(<MyNotes spaceId="s1" />)
    await screen.findByLabelText('Note content')
    fireEvent.click(screen.getByText(/Summarise/))
    await waitFor(() =>
      expect(mocked.enhanceNote).toHaveBeenCalledWith(1, 'summarize'),
    )
    expect(await screen.findByText('short summary')).toBeInTheDocument()

    fireEvent.click(screen.getByText('＋ Append to note'))
    expect(screen.getByLabelText('Note content')).toHaveValue(
      'Cells have a nucleus.\n\nshort summary',
    )
    await waitFor(() => expect(mocked.updateUserNote).toHaveBeenCalled(), {
      timeout: 2500,
    })
  })

  it('shows a friendly error when the AI call fails', async () => {
    mocked.enhanceNote.mockRejectedValue(
      new Error('The AI could not help right now: quota'),
    )
    render(<MyNotes spaceId="s1" />)
    await screen.findByLabelText('Note content')
    fireEvent.click(screen.getByText(/Summarise/))
    expect(await screen.findByRole('alert')).toHaveTextContent('quota')
  })
})
