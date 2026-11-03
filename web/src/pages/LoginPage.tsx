import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAppDispatch, useAppSelector } from '../app/hooks'
import { login, loginWithGoogle } from '../auth/authSlice'

export function LoginPage() {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const location = useLocation()
  const { user, error, pendingConfirmationFor } = useAppSelector((s) => s.auth)
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const from = (location.state as { from?: string } | null)?.from ?? '/'

  if (user) return <Navigate to={from} replace />
  if (pendingConfirmationFor) return <Navigate to="/register?step=confirm" replace />

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setBusy(true)
    const result = await dispatch(login({ email, password }))
    setBusy(false)
    if (login.fulfilled.match(result) && result.payload.user) navigate(from, { replace: true })
  }

  return (
    <section className="card narrow">
      <h1>Log in</h1>
      <button type="button" className="google" onClick={() => dispatch(loginWithGoogle())}>
        Continue with Google
      </button>
      <p className="divider">or</p>
      <form onSubmit={onSubmit}>
        <label>
          Email
          <input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </label>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <button type="submit" disabled={busy}>
          {busy ? 'Logging in…' : 'Log in'}
        </button>
      </form>
      <p className="muted">
        New here? <Link to="/register">Create an account</Link>
      </p>
    </section>
  )
}
