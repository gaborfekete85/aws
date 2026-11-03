import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { mockFetch } from '../../test/fetchMock'
import { renderWithProviders, signedIn, users } from '../../test/render'
import { AdminPage } from './AdminPage'

const people = [
  { username: 'u-ada', sub: 'u-ada', email: 'ada@example.com', name: 'Ada', enabled: true, status: 'CONFIRMED', roles: [] },
  { username: 'u-olga', sub: 'u-olga', email: 'olga@example.com', name: 'Olga', enabled: true, status: 'CONFIRMED', roles: ['organizer'] },
  { username: 'u-adam', sub: 'u-adam', email: 'adam@example.com', name: 'Adam', enabled: true, status: 'CONFIRMED', roles: ['admin'] },
]

describe('AdminPage', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('lists users with their roles', async () => {
    mockFetch({ 'GET /admin/users': () => ({ items: people, next_token: null }) })
    renderWithProviders(<AdminPage />, { preloadedState: signedIn(users.admin) })

    expect(await screen.findByText('ada@example.com')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Make Organizer: ada@example.com' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Revoke Organizer: olga@example.com' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /adam@example.com/ })).toBeNull() // Admins are not editable
  })

  it('grants the Organizer role and refreshes the list', async () => {
    let organizer = false
    const { calls } = mockFetch({
      'GET /admin/users': () => ({
        items: [{ ...people[0], roles: organizer ? ['organizer'] : [] }],
        next_token: null,
      }),
      'PUT /admin/users/:username/roles/organizer': () => {
        organizer = true
        return { ...people[0], roles: ['organizer'] }
      },
    })
    const user = userEvent.setup()
    renderWithProviders(<AdminPage />, { preloadedState: signedIn(users.admin) })

    await user.click(await screen.findByRole('button', { name: 'Make Organizer: ada@example.com' }))
    expect(await screen.findByRole('button', { name: 'Revoke Organizer: ada@example.com' })).toBeInTheDocument()
    expect(calls.some((c) => c.method === 'PUT' && c.path === '/admin/users/u-ada/roles/organizer')).toBe(true)
  })

  it('revokes with DELETE', async () => {
    const { calls } = mockFetch({
      'GET /admin/users': () => ({ items: [people[1]], next_token: null }),
      'DELETE /admin/users/:username/roles/organizer': () => ({ ...people[1], roles: [] }),
    })
    const user = userEvent.setup()
    renderWithProviders(<AdminPage />, { preloadedState: signedIn(users.admin) })
    await user.click(await screen.findByRole('button', { name: 'Revoke Organizer: olga@example.com' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'DELETE')).toBe(true))
  })

  it('searches by email', async () => {
    const { calls } = mockFetch({ 'GET /admin/users': () => ({ items: [], next_token: null }) })
    const user = userEvent.setup()
    renderWithProviders(<AdminPage />, { preloadedState: signedIn(users.admin) })
    await user.type(screen.getByLabelText('Search by email'), 'bo')
    await waitFor(() => expect(calls.some((c) => c.search === '?search=bo')).toBe(true))
    expect(await screen.findByText('No users match.')).toBeInTheDocument()
  })

  it('sends the ID token', async () => {
    window.localStorage.setItem('meeton.fakeAuth', JSON.stringify(users.admin))
    const { calls } = mockFetch({ 'GET /admin/users': () => ({ items: [], next_token: null }) })
    renderWithProviders(<AdminPage />, { preloadedState: signedIn(users.admin) })
    await waitFor(() => expect(calls.length).toBeGreaterThan(0))
    expect(calls[0].auth).toMatch(/^Bearer /)
  })
})
