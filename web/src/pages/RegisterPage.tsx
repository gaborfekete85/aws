import { useState, type FormEvent } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import { useAppDispatch, useAppSelector } from '../app/hooks'
import { confirmRegistration, register } from '../auth/authSlice'

export function RegisterPage() {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const { error, pendingConfirmationFor } = useAppSelector((s) => s.auth)
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [code, setCode] = useState('')
  const confirming = Boolean(pendingConfirmationFor) || params.get('step') === 'confirm'

  async function onRegister(e: FormEvent) {
    e.preventDefault()
    await dispatch(register({ email, password, name }))
  }

  async function onConfirm(e: FormEvent) {
    e.preventDefault()
    const result = await dispatch(
      confirmRegistration({ email: pendingConfirmationFor ?? email, code }),
    )
    if (confirmRegistration.fulfilled.match(result)) navigate('/login', { replace: true })
  }

  if (confirming) {
    return (
      <section className="card narrow">
        <h1>Check your email</h1>
        <p>We sent a verification code to {pendingConfirmationFor ?? 'your email'}.</p>
        <form onSubmit={onConfirm}>
          <label>
            Verification code
            <input inputMode="numeric" required value={code} onChange={(e) => setCode(e.target.value)} />
          </label>
          {error && (
            <p role="alert" className="error">
              {error}
            </p>
          )}
          <button type="submit">Verify</button>
        </form>
      </section>
    )
  }

  return (
    <section className="card narrow">
      <h1>Create an account</h1>
      <form onSubmit={onRegister}>
        <label>
          Name
          <input autoComplete="name" required value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label>
          Email
          <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          Password
          <input
            type="password"
            autoComplete="new-password"
            minLength={12}
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
          <small className="muted">At least 12 characters, with upper- and lowercase letters and a number.</small>
        </label>
        {error && (
          <p role="alert" className="error">
            {error}
          </p>
        )}
        <button type="submit">Sign up</button>
      </form>
      <p className="muted">
        Already registered? <Link to="/login">Log in</Link>
      </p>
    </section>
  )
}
