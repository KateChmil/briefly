import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import type { ChatMessage, SpaceStatus } from '../types'

interface Props {
  messages: ChatMessage[]
  status: SpaceStatus
  /** Resolves true when the message was accepted, false if sending failed. */
  onSend: (content: string) => Promise<boolean>
  sending: boolean
}

const INTERVIEW_CHIPS = [
  'My final exam is in 3 weeks',
  'I can study about 8 hours a week',
  'I struggle most with the hardest topics',
]
const TUTOR_CHIPS = [
  'Quiz me on the key concepts',
  'Explain the hardest topic simply',
  'I only have 4 hours a week now',
]

function Avatar({ assistant }: { assistant: boolean }) {
  return assistant ? (
    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-indigo-600 to-violet-600 text-xs font-bold text-white">
      B
    </span>
  ) : (
    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-200 text-xs text-slate-600">
      You
    </span>
  )
}

function TypingDots({ label }: { label: string }) {
  return (
    <div className="flex items-end gap-2">
      <Avatar assistant />
      <div className="flex items-center gap-2 rounded-2xl rounded-bl-md bg-white px-4 py-3 shadow-sm ring-1 ring-slate-200/70">
        <div className="flex gap-1" aria-hidden>
          {[0, 1, 2].map((i) => (
            <span
              key={i}
              className="h-1.5 w-1.5 animate-dot-bounce rounded-full bg-indigo-400"
              style={{ animationDelay: `${i * 0.15}s` }}
            />
          ))}
        </div>
        <span className="text-xs text-slate-500">{label}</span>
      </div>
    </div>
  )
}

export default function ChatPanel({ messages, status, onSend, sending }: Props) {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const generating = status === 'generating'

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length, sending, generating])

  const submit = async (text = input) => {
    const content = text.trim()
    if (!content || sending || generating) return
    setInput('')
    const ok = await onSend(content)
    if (!ok) setInput(content) // don't lose what they typed if it failed
    inputRef.current?.focus()
  }

  const chips = status === 'interviewing' ? INTERVIEW_CHIPS : TUTOR_CHIPS
  const showChips = !generating && !sending && messages.filter((m) => m.role === 'user').length < 2

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
        {messages.map((m) => {
          const assistant = m.role === 'assistant'
          return (
            <div
              key={m.id}
              className={`animate-slide-up flex items-end gap-2 ${assistant ? '' : 'flex-row-reverse'}`}
            >
              <Avatar assistant={assistant} />
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
                  assistant
                    ? 'rounded-bl-md bg-white text-slate-800 shadow-sm ring-1 ring-slate-200/70'
                    : 'rounded-br-md bg-gradient-to-br from-indigo-600 to-violet-600 text-white'
                }`}
              >
                {assistant ? (
                  <div className="md">
                    <ReactMarkdown>{m.content}</ReactMarkdown>
                  </div>
                ) : (
                  <p className="whitespace-pre-wrap">{m.content}</p>
                )}
              </div>
            </div>
          )
        })}
        {sending && <TypingDots label="Thinking…" />}
        {generating && !sending && (
          <TypingDots label="Building your plan, notes, test and flashcards…" />
        )}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-slate-200 bg-white p-3">
        {showChips && (
          <div className="mb-2 flex flex-wrap gap-1.5">
            {chips.map((c) => (
              <button
                key={c}
                onClick={() => {
                  setInput(c)
                  inputRef.current?.focus()
                }}
                className="rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700 transition hover:bg-indigo-100"
              >
                {c}
              </button>
            ))}
          </div>
        )}
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                void submit()
              }
            }}
            rows={2}
            maxLength={8000}
            disabled={generating}
            placeholder={
              generating
                ? 'Hang tight — generating your materials…'
                : status === 'interviewing'
                  ? 'Tell Briefly about your exam, level and weekly hours…'
                  : 'Ask a question, or tell me if your plans change…'
            }
            aria-label="Message"
            className="flex-1 resize-none rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-sm outline-none transition placeholder:text-slate-400 focus:border-indigo-400 focus:bg-white focus:ring-2 focus:ring-indigo-100 disabled:opacity-60"
          />
          <button
            onClick={() => void submit()}
            disabled={!input.trim() || sending || generating}
            aria-label="Send"
            className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-gradient-to-r from-indigo-600 to-violet-600 text-white shadow-sm transition hover:from-indigo-500 hover:to-violet-500 disabled:cursor-not-allowed disabled:opacity-40"
          >
            ➤
          </button>
        </div>
      </div>
    </div>
  )
}
