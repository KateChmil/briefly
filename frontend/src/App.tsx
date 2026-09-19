import { Route, Routes } from 'react-router-dom'
import SpacesPage from './pages/SpacesPage'
import SpacePage from './pages/SpacePage'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<SpacesPage />} />
      <Route path="/spaces/:spaceId" element={<SpacePage />} />
    </Routes>
  )
}
