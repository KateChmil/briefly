import { useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import type { Quiz } from '../types'
import { Button } from './ui'

export default function QuizView({ content }: { content: string }) {
  const quiz: Quiz | null = useMemo(() => {
    try {
      const parsed = JSON.parse(content)
      if (parsed && Array.isArray(parsed.questions)) return parsed as Quiz
      return null
    } catch {
      return null
    }
  }, [content])

  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [checked, setChecked] = useState(false)

  if (!quiz) {
    return (
      <div className="prose-sm text-slate-800">
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    )
  }

  const isCorrect = (i: number) => {
    const q = quiz.questions[i]
    const a = (answers[i] ?? '').trim().toLowerCase()
    return a === q.answer.trim().toLowerCase()
  }
  const score = quiz.questions.filter((_, i) => isCorrect(i)).length

  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <h3 className="font-semibold text-slate-900">{quiz.title}</h3>
        {checked && (
          <span className="text-sm font-medium text-slate-600">
            Score: {score}/{quiz.questions.length}
          </span>
        )}
      </div>

      <ol className="space-y-5">
        {quiz.questions.map((q, i) => {
          const answered = (answers[i] ?? '') !== ''
          const correct = isCorrect(i)
          return (
            <li
              key={i}
              className={`rounded-lg border bg-white p-4 ${
                checked
                  ? correct
                    ? 'border-green-300'
                    : answered
                      ? 'border-red-300'
                      : 'border-slate-200'
                  : 'border-slate-200'
              }`}
            >
              <p className="mb-2 text-sm font-medium text-slate-800">
                {i + 1}. {q.question}
              </p>

              {q.type === 'mcq' && q.choices ? (
                <div className="space-y-1">
                  {q.choices.map((c) => (
                    <label
                      key={c}
                      className="flex items-center gap-2 text-sm text-slate-700"
                    >
                      <input
                        type="radio"
                        name={`q${i}`}
                        disabled={checked}
                        checked={answers[i] === c}
                        onChange={() =>
                          setAnswers((a) => ({ ...a, [i]: c }))
                        }
                      />
                      {c}
                    </label>
                  ))}
                </div>
              ) : (
                <input
                  type="text"
                  disabled={checked}
                  value={answers[i] ?? ''}
                  onChange={(e) =>
                    setAnswers((a) => ({ ...a, [i]: e.target.value }))
                  }
                  placeholder="Your answer..."
                  className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-sm outline-none focus:border-indigo-500"
                />
              )}

              {checked && (
                <div className="mt-2 rounded-lg bg-slate-50 p-2 text-xs text-slate-600">
                  <p>
                    <span className="font-medium">Answer:</span> {q.answer}
                  </p>
                  {q.explanation && <p className="mt-1">{q.explanation}</p>}
                </div>
              )}
            </li>
          )
        })}
      </ol>

      <div className="mt-4 flex gap-2">
        {!checked ? (
          <Button
            onClick={() => setChecked(true)}
            disabled={Object.keys(answers).length === 0}
          >
            Check answers
          </Button>
        ) : (
          <Button
            variant="ghost"
            onClick={() => {
              setAnswers({})
              setChecked(false)
            }}
          >
            Try again
          </Button>
        )}
      </div>
    </div>
  )
}
