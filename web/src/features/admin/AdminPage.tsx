import { useEffect, useState } from 'react'
import { useListUsersQuery, useSetOrganizerMutation, type AdminUser } from './adminApi'

function useDebounced<T>(value: T, ms = 300): T {
  const [debounced, setDebounced] = useState(value)
  useEffect(() => {
    const id = setTimeout(() => setDebounced(value), ms)
    return () => clearTimeout(id)
  }, [value, ms])
  return debounced
}

function OrganizerToggle({ user }: { user: AdminUser }) {
  const [setOrganizer, { isLoading, error }] = useSetOrganizerMutation()
  const isOrganizer = user.roles.includes('organizer')
  const label = isOrganizer ? 'Revoke Organizer' : 'Make Organizer'
  return (
    <>
      <button
        type="button"
        className={isOrganizer ? 'secondary' : undefined}
        disabled={isLoading}
        aria-label={`${label}: ${user.email}`}
        onClick={() => setOrganizer({ username: user.username, organizer: !isOrganizer })}
      >
        {isLoading ? 'Saving…' : label}
      </button>
      {error && (
        <span role="alert" className="error">
          {' '}
          Could not update
        </span>
      )}
    </>
  )
}

export function AdminPage() {
  const [search, setSearch] = useState('')
  const debounced = useDebounced(search.trim())
  const { data, isFetching, error } = useListUsersQuery({ search: debounced || undefined })

  return (
    <section>
      <h1>Users and roles</h1>
      <p className="muted">
        Organizers create and manage Events. Role changes apply the next time the user signs in.
      </p>
      <label>
        Search by email
        <input
          type="search"
          placeholder="ada@"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </label>
      {error && (
        <p role="alert" className="error">
          Could not load users.
        </p>
      )}
      <table className="table" aria-busy={isFetching}>
        <thead>
          <tr>
            <th>Name</th>
            <th>Email</th>
            <th>Roles</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {data?.items.map((user) => (
            <tr key={user.username}>
              <td>{user.name || '—'}</td>
              <td>{user.email}</td>
              <td>{user.roles.length ? user.roles.join(', ') : 'Attendee'}</td>
              <td>{user.roles.includes('admin') ? <span className="muted">Admin</span> : <OrganizerToggle user={user} />}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {data && data.items.length === 0 && <p className="muted">No users match.</p>}
    </section>
  )
}
