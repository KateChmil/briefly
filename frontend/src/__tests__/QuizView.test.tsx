import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import QuizView from '../components/QuizView'

const quiz = JSON.stringify({
  title: 'Bio quiz',
  questions: [
    {
      type: 'mcq',
      question: 'Which organelle makes ATP?',
      choices: ['Nucleus', 'Mitochondria', 'Ribosome'],
      answer: 'Mitochondria',
      explanation: 'Site of cellular respiration.',
    },
    {
      type: 'short',
      question: 'What does DNA stand for?',
      answer: 'Deoxyribonucleic acid',
      explanation: '',
    },
  ],
})

describe('QuizView', () => {
  it('renders questions and scores answers', () => {
    render(<QuizView content={quiz} />)
    expect(screen.getByText('Bio quiz')).toBeInTheDocument()

    fireEvent.click(screen.getByLabelText('Mitochondria'))
    fireEvent.change(screen.getByPlaceholderText('Your answer...'), {
      target: { value: 'wrong' },
    })
    fireEvent.click(screen.getByText('Check answers'))

    expect(screen.getByText('Score: 1/2')).toBeInTheDocument()
    expect(
      screen.getAllByText('Answer:', { exact: false }).length,
    ).toBeGreaterThan(0)
  })

  it('resets on Try again', () => {
    render(<QuizView content={quiz} />)
    fireEvent.click(screen.getByLabelText('Nucleus'))
    fireEvent.click(screen.getByText('Check answers'))
    fireEvent.click(screen.getByText('Try again'))
    expect(screen.queryByText(/Score:/)).not.toBeInTheDocument()
  })

  it('falls back to markdown for invalid JSON', () => {
    render(<QuizView content="# Not a quiz" />)
    expect(screen.getByText('Not a quiz')).toBeInTheDocument()
  })
})

describe('QuizView robustness', () => {
  it('skips malformed questions instead of crashing', () => {
    const messy = JSON.stringify({
      title: 'Messy',
      questions: [
        { type: 'short', question: 'Fine?', answer: 'yes' },
        { type: 'mcq', question: 'No answer field' },
        null,
        { type: 'mcq', question: 'Bad choices', choices: 'nope', answer: 'x' },
      ],
    })
    render(<QuizView content={messy} />)
    expect(screen.getByText(/1\. Fine\?/)).toBeInTheDocument()
    expect(screen.getByText(/2\. Bad choices/)).toBeInTheDocument() // degrades to a text answer
    expect(screen.queryByText(/No answer field/)).not.toBeInTheDocument()
  })

  it('does not count an unanswered question as correct', () => {
    render(<QuizView content={quiz} />)
    fireEvent.click(screen.getByLabelText('Mitochondria'))
    fireEvent.click(screen.getByText('Check answers'))
    expect(screen.getByText(/Score: 1\/2/)).toBeInTheDocument()
  })
})
