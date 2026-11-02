import { Route, Routes } from 'react-router-dom'
import { useAppSelector } from './app/hooks'

export default function App() {
  const name = useAppSelector((s) => s.app.name)
  return (
    <main>
      <h1>{name}</h1>
      <Routes>
        <Route path="/" element={<p>Find local Events near you.</p>} />
      </Routes>
    </main>
  )
}
