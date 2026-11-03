import { useEffect } from 'react'
import { Route, Routes } from 'react-router-dom'
import { useAppDispatch } from './app/hooks'
import { loadSession } from './auth/authSlice'
import { NavBar } from './components/NavBar'
import { RequireRole } from './components/RequireRole'
import { AuthCallbackPage } from './pages/AuthCallbackPage'
import { HomePage } from './pages/HomePage'
import { LoginPage } from './pages/LoginPage'
import { Placeholder } from './pages/Placeholder'
import { RegisterPage } from './pages/RegisterPage'

export default function App() {
  const dispatch = useAppDispatch()
  useEffect(() => {
    void dispatch(loadSession())
  }, [dispatch])

  return (
    <>
      <NavBar />
      <main>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/auth/callback" element={<AuthCallbackPage />} />
          <Route
            path="/me/bookings"
            element={
              <RequireRole>
                <Placeholder title="My Bookings" />
              </RequireRole>
            }
          />
          <Route
            path="/organizer/*"
            element={
              <RequireRole role="organizer">
                <Placeholder title="Organizer dashboard" />
              </RequireRole>
            }
          />
          <Route
            path="/admin"
            element={
              <RequireRole role="admin">
                <Placeholder title="Admin" />
              </RequireRole>
            }
          />
          <Route path="*" element={<Placeholder title="Page not found" />} />
        </Routes>
      </main>
    </>
  )
}
