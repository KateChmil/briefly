import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import FlashcardsView, { parseCards } from '../components/FlashcardsView'

const content = JSON.stringify({
  cards: [
    { front: 'Powerhouse of the cell?', back: 'Mitochondria' },
    { front: 'DNA stands for?', back: 'Deoxyribonucleic acid' },
  ],
})

describe('parseCards', () => {
  it('keeps well-formed cards and ignores junk', () => {
    const raw = JSON.stringify({ cards: [{ front: 'a', back: 'b' }, { front: 1 }, null, 'x'] })
    expect(parseCards(raw)).toEqual([{ front: 'a', back: 'b' }])
    expect(parseCards('not json')).toEqual([])
    expect(parseCards('{}')).toEqual([])
  })
})

describe('FlashcardsView', () => {
  it('walks through the deck and summarises the result', () => {
    render(<FlashcardsView content={content} />)
    expect(screen.getByText('Card 1 of 2')).toBeInTheDocument()

    fireEvent.click(screen.getByText('Show answer'))
    fireEvent.click(screen.getByText(/Got it/))
    expect(screen.getByText('Card 2 of 2')).toBeInTheDocument()

    fireEvent.click(screen.getByText('Show answer'))
    fireEvent.click(screen.getByText(/Review again/))

    expect(screen.getByText('You knew 1 of 2')).toBeInTheDocument()
    expect(screen.getByText('Review missed')).toBeInTheDocument()
  })

  it('shows an empty state when there are no valid cards', () => {
    render(<FlashcardsView content="{}" />)
    expect(screen.getByText(/No flashcards yet/)).toBeInTheDocument()
  })
})
