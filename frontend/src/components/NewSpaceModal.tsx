import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useSpaces } from '../lib/spaces'
import { Button, ErrorNote, Modal, inputClass } from './ui'

const IDEAS = ['Calculus II', 'Biology 101', 'Data Structures', 'Organic Chemistry']

export default function NewSpaceModal({ onClose }: { onClose: () => void }) {
  const [name, setName] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const navigate = useNavigate()
  const { reload } = useSpaces()

  const create = async () => {
    const trimmed = name.trim()
    if (!trimmed || busy) return
    setBusy(true)
    setError('')
    try {
      const space = await api.createSpace(trimmed)
      await reload()
      onClose()
      navigate(`/spaces/${space.id}`)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create space')
      setBusy(false)
    }
  }

  return (
    <Modal title="New subject space" onClose={onClose}>
      <p className="mb-3 text-sm text-slate-500">
        A space holds one subject: its materials, chat, study plan, notes and quizzes.
      </p>
      <input
        autoFocus
        value={name}
        maxLength={200}
        onChange={(e) => setName(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && create()}
        placeholder="e.g. Biology 101"
        className={`${inputClass} mb-3`}
      />
      <div className="mb-4 flex flex-wrap gap-1.5">
        {IDEAS.map((idea) => (
          <button
            key={idea}
            onClick={() => setName(idea)}
            className="rounded-full bg-slate-100 px-2.5 py-1 text-xs text-slate-600 transition hover:bg-indigo-50 hover:text-indigo-700"
          >
            {idea}
          </button>
        ))}
      </div>
      {error && <div className="mb-3"><ErrorNote>{error}</ErrorNote></div>}
      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onClose}>
          Cancel
        </Button>
        <Button onClick={create} disabled={!name.trim() || busy}>
          {busy ? 'Creating…' : 'Create space'}
        </Button>
      </div>
    </Modal>
  )
}
