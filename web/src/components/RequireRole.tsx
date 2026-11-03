import type { ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { useAppSelector } from '../app/hooks'
import type { Role } from '../auth'

/** Gate a route: signed-in users only, optionally with a role (Admins pass every role). */
export function RequireRole({ role, children }: { role?: Role; children: ReactNode }) {
  const { status, user } = useAppSelector((s) => s.auth)
  const location = useLocation()

  if (status === 'unknown' || status === 'loading') return <p className="muted">Loading…</p>
  if (!user) return <Navigate to="/login" replace state={{ from: location.pathname }} />
  if (role && !user.groups.includes(role) && !user.groups.includes('admin')) {
    return (
      <section>
        <h1>Not allowed</h1>
        <p>This page needs the {role} role.</p>
      </section>
    )
  }
  return <>{children}</>
}
