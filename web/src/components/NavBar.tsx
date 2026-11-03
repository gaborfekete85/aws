import { Link, NavLink } from 'react-router-dom'
import { useAppDispatch, useAppSelector } from '../app/hooks'
import { logout, selectIsAdmin, selectIsOrganizer, selectUser } from '../auth/authSlice'

/** Visitors see search; Attendees add My Bookings; Organizers add the dashboard; Admins add Admin. */
export function NavBar() {
  const dispatch = useAppDispatch()
  const user = useAppSelector(selectUser)
  const isOrganizer = useAppSelector(selectIsOrganizer)
  const isAdmin = useAppSelector(selectIsAdmin)

  return (
    <header className="nav">
      <Link to="/" className="brand">
        Localbini
      </Link>
      <nav aria-label="Main">
        <NavLink to="/">Find Events</NavLink>
        {user && <NavLink to="/me/bookings">My Bookings</NavLink>}
        {isOrganizer && <NavLink to="/organizer">Organizer</NavLink>}
        {isAdmin && <NavLink to="/admin">Admin</NavLink>}
      </nav>
      <div className="nav-user">
        {user ? (
          <>
            <span className="muted" data-testid="signed-in-as">
              {user.name ?? user.email}
            </span>
            <button type="button" className="link" onClick={() => dispatch(logout())}>
              Log out
            </button>
          </>
        ) : (
          <>
            <NavLink to="/login">Log in</NavLink>
            <NavLink to="/register" className="button">
              Sign up
            </NavLink>
          </>
        )}
      </div>
    </header>
  )
}
