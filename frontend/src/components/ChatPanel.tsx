import { useEffect, useRef, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import type { ChatMessage } from '../types'
import { Button } from './ui'

interface Props {
  messages: ChatMessage[]
  onSend: (content: string) => Promise<void>
  sending: boolean
  generating: boolean
}

export default function ChatPanel({ messages, onSend, sending, generating }: Props) {
  const [input, setInput] = useState('')
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length, sending])

  const submit = async () => {
    const text = input.trim()
    if (!text || sending) return
    setInput('')
    await onSend(text)
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="border-b border-slate-200 px-4 py-2 text-sm font-medium text-slate-600">
        Chat with your study assistant
      </div>

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4">
        {messages.map((m) => (
          <div
            key={m.id}
            className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}
          >
            <div
              className={`max-w-[85%] rounded-2xl px-4 py-2 text-sm ${
                m.role === 'user'
                  ? 'bg-indigo-600 text-white'
                  : 'bg-slate-100 text-slate-800'
              }`}
            >
              {m.role === 'assistant' ? (
                <div className="prose-sm [&_p]:my-1 [&_ul]:my-1">
                  <ReactMarkdown>{m.content}</ReactMarkdown>
                </div>
              ) : (
                m.content
              )}
            </div>
          </div>
        ))}
        {sending && (
          <div className="flex justify-start">
            <div className="rounded-2xl bg-slate-100 px-4 py-2 text-sm text-slate-500">
              Thinking...
            </div>
          </div>
        )}
        {generating && (
          <div className="flex justify-start">
            <div className="rounded-2xl bg-amber-50 px-4 py-2 text-sm text-amber-700">
              Generating your study plan, notes and sample test — this takes a
              moment.
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <div className="border-t border-slate-200 p-3">
        <div className="flex gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                submit()
              }
            }}
            rows={2}
            placeholder="Type your answer or ask a question..."
            className="flex-1 resize-none rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-indigo-500"
          />
          <Button onClick={submit} disabled={!input.trim() || sending}>
            Send
          </Button>
        </div>
      </div>
    </div>
  )
}
