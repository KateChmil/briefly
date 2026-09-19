import { useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import type { Quiz, QuizQuestion } from '../types'
import { Button, ProgressBar } from './ui'

/** Accept whatever JSON we were given, keeping only well-formed questions. */
function parseQuiz(content: string): Quiz | null {
  try {
    const parsed = JSON.parse(content)
    if (!parsed || !Array.isArray(parsed.questions)) return null
    const questions: QuizQuestion[] = []
    for (const q of parsed.questions) {
      if (!q || typeof q.question !== 'string' || q.answer == null) continue
      const choices = Array.isArray(q.choices) ? q.choices.map(String) : undefined
      questions.push({
        type: q.type === 'mcq' && choices && choices.length > 1 ? 'mcq' : 'short',
        question: q.question,
        choices,
        answer: String(q.answer),
        explanation: typeof q.explanation === 'string' ? q.explanation : '',
      })
    }
    return questions.length
      ? { title: String(parsed.title ?? 'Sample test'), questions }
      : null
  } catch {
    return null
  }
}

export default function QuizView({ content }: { content: string }) {
  const quiz = useMemo(() => parseQuiz(content), [content])
  const [answers, setAnswers] = useState<Record<number, string>>({})
  const [checked, setChecked] = useState(false)

  if (!quiz) {
    return (
      <div className="md">
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    )
  }

  const isCorrect = (i: number) => {
    const a = (answers[i] ?? '').trim().toLowerCase()
    return a !== '' && a === quiz.questions[i].answer.trim().toLowerCase()
  }
  const score = quiz.questions.filter((_, i) => isCorrect(i)).length
  const answered = Object.values(answers).filter((a) => a.trim() !== '').length
  const pct = Math.round((score / quiz.questions.length) * 100)

  return (
    <div>
      <div className="mb-4 rounded-2xl bg-gradient-to-br from-indigo-50 to-violet-50 p-4 ring-1 ring-indigo-100">
        <div className="mb-2 flex items-center justify-between gap-2">
          <h3 className="font-semibold text-slate-900">{quiz.title}</h3>
          {checked ? (
            <span className="text-sm font-semibold text-indigo-700">
              <span>
                Score: {score}/{quiz.questions.length}
              </span>{' '}
              <span className="font-normal text-slate-500">({pct}%)</span>
            </span>
          ) : (
            <span className="text-xs text-slate-500">
              {answered}/{quiz.questions.length} answered
            </span>
          )}
        </div>
        <ProgressBar value={checked ? score : answered} max={quiz.questions.length} />
        {checked && (
          <p className="mt-2 text-sm text-slate-600">
            {pct >= 80
              ? '🎉 Excellent! You are well prepared.'
              : pct >= 50
                ? '👍 Solid start — review the ones you missed.'
                : '💪 Keep going — check the explanations and try again.'}
          </p>
        )}
      </div>

      <ol className="space-y-3">
        {quiz.questions.map((q, i) => {
          const wasAnswered = (answers[i] ?? '').trim() !== ''
          const correct = isCorrect(i)
          return (
            <li
              key={i}
              className={`rounded-2xl bg-white p-4 ring-1 transition ${
                checked
                  ? correct
                    ? 'ring-emerald-300'
                    : wasAnswered
                      ? 'ring-rose-300'
                      : 'ring-slate-200'
                  : 'ring-slate-200/70'
              }`}
            >
              <p className="mb-2.5 text-sm font-medium text-slate-800">
                {i + 1}. {q.question}
              </p>

              {q.type === 'mcq' && q.choices ? (
                <div className="space-y-1">
                  {q.choices.map((c) => (
                    <label
                      key={c}
                      className={`flex cursor-pointer items-center gap-2.5 rounded-xl px-3 py-2 text-sm transition ${
                        answers[i] === c ? 'bg-indigo-50 text-indigo-800' : 'text-slate-700 hover:bg-slate-50'
                      }`}
                    >
                      <input
                        type="radio"
                        name={`q${i}`}
                        className="accent-indigo-600"
                        disabled={checked}
                        checked={answers[i] === c}
                        onChange={() => setAnswers((a) => ({ ...a, [i]: c }))}
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
                  onChange={(e) => setAnswers((a) => ({ ...a, [i]: e.target.value }))}
                  placeholder="Your answer..."
                  className="w-full rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-100 disabled:bg-slate-50"
                />
              )}

              {checked && (
                <div
                  className={`mt-3 rounded-xl p-3 text-xs ${
                    correct ? 'bg-emerald-50 text-emerald-800' : 'bg-slate-50 text-slate-600'
                  }`}
                >
                  <p>
                    {correct ? '✅ ' : wasAnswered ? '❌ ' : '➖ '}
                    <span className="font-semibold">Answer:</span> {q.answer}
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
          <Button onClick={() => setChecked(true)} disabled={answered === 0}>
            Check answers
          </Button>
        ) : (
          <Button
            variant="secondary"
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
