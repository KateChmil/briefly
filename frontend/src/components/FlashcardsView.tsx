import { useEffect, useMemo, useState } from 'react'
import type { Flashcard } from '../types'
import { Button, ProgressBar } from './ui'

export function parseCards(content: string): Flashcard[] {
  try {
    const parsed = JSON.parse(content)
    const raw: unknown[] = Array.isArray(parsed?.cards) ? parsed.cards : []
    return raw.flatMap((c) => {
      const card = c as { front?: unknown; back?: unknown }
      return typeof card?.front === 'string' && typeof card?.back === 'string'
        ? [{ front: card.front, back: card.back }]
        : []
    })
  } catch {
    return []
  }
}

function shuffled<T>(list: T[]): T[] {
  const a = [...list]
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1))
    ;[a[i], a[j]] = [a[j], a[i]]
  }
  return a
}

export default function FlashcardsView({ content }: { content: string }) {
  const all = useMemo(() => parseCards(content), [content])
  const [deck, setDeck] = useState<Flashcard[]>(all)
  const [index, setIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [known, setKnown] = useState(0)
  const [missed, setMissed] = useState<Flashcard[]>([])

  const restart = (cards: Flashcard[]) => {
    setDeck(cards)
    setIndex(0)
    setFlipped(false)
    setKnown(0)
    setMissed([])
  }

  // a regenerated deck replaces whatever we were studying
  useEffect(() => restart(all), [all])

  const finished = deck.length > 0 && index >= deck.length
  const card = deck[index]

  const answer = (gotIt: boolean) => {
    if (gotIt) setKnown((k) => k + 1)
    else setMissed((m) => [...m, card])
    setFlipped(false)
    setIndex((i) => i + 1)
  }

  if (all.length === 0) {
    return <p className="text-sm text-slate-500">No flashcards yet — hit Regenerate.</p>
  }

  if (finished) {
    return (
      <div className="animate-pop-in rounded-2xl bg-gradient-to-br from-indigo-50 to-violet-50 p-8 text-center ring-1 ring-indigo-100">
        <div className="mb-2 text-4xl">{missed.length === 0 ? '🏆' : '🎯'}</div>
        <h3 className="text-lg font-semibold text-slate-900">
          You knew {known} of {deck.length}
        </h3>
        <p className="mt-1 text-sm text-slate-600">
          {missed.length === 0
            ? 'Perfect run! Shuffle the deck to keep it fresh.'
            : `${missed.length} card${missed.length === 1 ? '' : 's'} to review.`}
        </p>
        <div className="mt-5 flex justify-center gap-2">
          {missed.length > 0 && (
            <Button onClick={() => restart(shuffled(missed))}>Review missed</Button>
          )}
          <Button variant="secondary" onClick={() => restart(shuffled(all))}>
            Shuffle all
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-3">
        <div className="mb-1 flex justify-between text-xs text-slate-500">
          <span>
            Card {index + 1} of {deck.length}
          </span>
          <span>✅ {known} · 🔁 {missed.length}</span>
        </div>
        <ProgressBar value={index} max={deck.length} />
      </div>

      <button
        onClick={() => setFlipped((f) => !f)}
        aria-label={flipped ? 'Show question' : 'Show answer'}
        className="[perspective:1200px] block h-64 w-full text-left"
      >
        <div
          className={`relative h-full w-full transition-transform duration-500 [transform-style:preserve-3d] ${
            flipped ? '[transform:rotateY(180deg)]' : ''
          }`}
        >
          <div className="absolute inset-0 flex flex-col items-center justify-center rounded-2xl bg-white p-6 text-center shadow-md ring-1 ring-slate-200 [backface-visibility:hidden]">
            <span className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-indigo-500">
              Question
            </span>
            <p className="text-lg font-medium text-slate-900">{card.front}</p>
            <span className="mt-4 text-xs text-slate-400">Click to flip</span>
          </div>
          <div className="absolute inset-0 flex flex-col items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-600 to-violet-600 p-6 text-center text-white shadow-md [backface-visibility:hidden] [transform:rotateY(180deg)]">
            <span className="mb-3 text-[11px] font-semibold uppercase tracking-widest text-indigo-200">
              Answer
            </span>
            <p className="text-base font-medium">{card.back}</p>
          </div>
        </div>
      </button>

      <div className="mt-4 flex justify-center gap-2">
        {flipped ? (
          <>
            <Button variant="secondary" onClick={() => answer(false)}>
              🔁 Review again
            </Button>
            <Button onClick={() => answer(true)}>✅ Got it</Button>
          </>
        ) : (
          <Button variant="secondary" onClick={() => setFlipped(true)}>
            Show answer
          </Button>
        )}
      </div>
    </div>
  )
}
