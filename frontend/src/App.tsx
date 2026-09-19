import { useState } from 'react'
import { Link, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import NewSpaceModal from './components/NewSpaceModal'
import { ErrorBoundary } from './components/ui'
import { SpacesProvider, useSpaces } from './lib/spaces'
import { spaceColor } from './lib/theme'
import CalendarPage from './pages/CalendarPage'
import DashboardPage from './pages/DashboardPage'
import SpacePage from './pages/SpacePage'

const navClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-medium transition ${
    isActive
      ? 'bg-indigo-50 text-indigo-700'
      : 'text-slate-600 hover:bg-slate-100 hover:text-slate-900'
  }`

function Logo() {
  return (
    <Link to="/" className="flex items-center gap-2">
      <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-600 to-violet-600 text-sm font-bold text-white shadow-sm">
        B
      </span>
      <span className="text-lg font-bold tracking-tight text-slate-900">Briefly</span>
    </Link>
  )
}

function Sidebar({ onNew }: { onNew: () => void }) {
  const { spaces } = useSpaces()
  return (
    <aside className="hidden w-64 shrink-0 flex-col border-r border-slate-200 bg-white md:flex">
      <div className="px-5 py-5">
        <Logo />
      </div>
      <nav className="flex flex-col gap-1 px-3">
        <NavLink to="/" end className={navClass}>
          <span>🏠</span> Dashboard
        </NavLink>
        <NavLink to="/calendar" className={navClass}>
          <span>🗓️</span> Calendar
        </NavLink>
      </nav>

      <div className="mt-6 flex items-center justify-between px-6">
        <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">
          Subjects
        </span>
        <button
          onClick={onNew}
          title="New subject"
          className="rounded-lg px-1.5 text-lg leading-none text-slate-400 transition hover:bg-slate-100 hover:text-indigo-600"
        >
          +
        </button>
      </div>
      <nav className="mt-2 flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto px-3 pb-4">
        {spaces?.map((s) => (
          <NavLink key={s.id} to={`/spaces/${s.id}`} className={navClass}>
            <span className={`h-2.5 w-2.5 shrink-0 rounded-full ${spaceColor(s.id).dot}`} />
            <span className="truncate">{s.name}</span>
          </NavLink>
        ))}
        {spaces?.length === 0 && (
          <button
            onClick={onNew}
            className="rounded-xl border border-dashed border-slate-300 px-3 py-3 text-left text-xs text-slate-500 hover:border-indigo-300 hover:text-indigo-600"
          >
            Create your first subject
          </button>
        )}
      </nav>
    </aside>
  )
}

function MobileBar({ onNew }: { onNew: () => void }) {
  return (
    <header className="flex h-14 shrink-0 items-center justify-between border-b border-slate-200 bg-white px-4 md:hidden">
      <Logo />
      <nav className="flex items-center gap-1 text-sm">
        <NavLink to="/" end className={navClass}>
          Home
        </NavLink>
        <NavLink to="/calendar" className={navClass}>
          Calendar
        </NavLink>
        <button
          onClick={onNew}
          className="ml-1 rounded-xl bg-indigo-600 px-3 py-1.5 font-medium text-white"
        >
          +
        </button>
      </nav>
    </header>
  )
}

function Shell() {
  const [newOpen, setNewOpen] = useState(false)
  const location = useLocation()
  return (
    <div className="flex h-dvh flex-col md:flex-row">
      <MobileBar onNew={() => setNewOpen(true)} />
      <Sidebar onNew={() => setNewOpen(true)} />
      <main className="min-h-0 min-w-0 flex-1 overflow-y-auto">
        {/* keyed by path so navigating away from a crashed page recovers */}
        <ErrorBoundary key={location.pathname}>
          <Routes>
            <Route path="/" element={<DashboardPage onNewSpace={() => setNewOpen(true)} />} />
            <Route path="/calendar" element={<CalendarPage />} />
            <Route path="/spaces/:spaceId" element={<SpacePage />} />
            <Route path="*" element={<DashboardPage onNewSpace={() => setNewOpen(true)} />} />
          </Routes>
        </ErrorBoundary>
      </main>
      {newOpen && <NewSpaceModal onClose={() => setNewOpen(false)} />}
    </div>
  )
}

export default function App() {
  return (
    <SpacesProvider>
      <Shell />
    </SpacesProvider>
  )
}
