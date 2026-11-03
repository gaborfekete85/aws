import { useEffect } from 'react'
import { Navigate } from 'react-router-dom'
import { useAppDispatch, useAppSelector } from '../app/hooks'
import { loadSession } from '../auth/authSlice'

/** Cognito Hosted UI (Google) redirects here; Amplify finishes the code exchange. */
export function AuthCallbackPage() {
  const dispatch = useAppDispatch()
  const status = useAppSelector((s) => s.auth.status)

  useEffect(() => {
    void dispatch(loadSession())
  }, [dispatch])

  if (status === 'signedIn') return <Navigate to="/" replace />
  if (status === 'signedOut') return <Navigate to="/login" replace />
  return <p className="muted">Signing you in…</p>
}
