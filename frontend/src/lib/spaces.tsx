import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from 'react'
import type { ReactNode } from 'react'
import { api } from '../api/client'
import type { SpaceSummary } from '../types'

interface SpacesValue {
  spaces: SpaceSummary[] | null
  error: string
  reload: () => Promise<void>
}

const SpacesContext = createContext<SpacesValue | null>(null)

/** Shared list of subject spaces, used by the sidebar and the dashboard. */
export function SpacesProvider({ children }: { children: ReactNode }) {
  const [spaces, setSpaces] = useState<SpaceSummary[] | null>(null)
  const [error, setError] = useState('')

  const reload = useCallback(async () => {
    try {
      setSpaces(await api.listSpaces())
      setError('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load spaces')
    }
  }, [])

  useEffect(() => {
    void reload()
  }, [reload])

  const value = useMemo(() => ({ spaces, error, reload }), [spaces, error, reload])
  return <SpacesContext.Provider value={value}>{children}</SpacesContext.Provider>
}

export function useSpaces(): SpacesValue {
  const ctx = useContext(SpacesContext)
  if (!ctx) throw new Error('useSpaces must be used inside <SpacesProvider>')
  return ctx
}
