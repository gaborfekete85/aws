import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { renderWithProviders, signedIn, users } from './test/render'

describe('App shell', () => {
  it('logs in with email and password and shows the role-aware nav', async () => {
    const user = userEvent.setup()
    renderWithProviders(<App />, { route: '/login' })

    await user.type(await screen.findByLabelText('Email'), 'organizer@example.com')
    await user.type(screen.getByLabelText('Password'), 'Password123!')
    await user.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByTestId('signed-in-as')).toHaveTextContent('organizer')
    expect(screen.getByRole('link', { name: 'Organizer' })).toBeInTheDocument()
  })

  it('shows the error on wrong credentials', async () => {
    const user = userEvent.setup()
    renderWithProviders(<App />, { route: '/login' })
    await user.type(await screen.findByLabelText('Email'), 'ada@example.com')
    await user.type(screen.getByLabelText('Password'), 'nope')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect username or password.')
  })

  it('logs out', async () => {
    const user = userEvent.setup()
    renderWithProviders(<App />, { route: '/login' })
    await user.type(await screen.findByLabelText('Email'), 'ada@example.com')
    await user.type(screen.getByLabelText('Password'), 'Password123!')
    await user.click(screen.getByRole('button', { name: 'Log in' }))
    await user.click(await screen.findByRole('button', { name: 'Log out' }))
    expect(await screen.findByRole('link', { name: 'Log in' })).toBeInTheDocument()
  })

  it('registers and confirms with a code', async () => {
    const user = userEvent.setup()
    renderWithProviders(<App />, { route: '/register' })
    await user.type(await screen.findByLabelText('Name'), 'New Person')
    await user.type(screen.getByLabelText('Email'), 'new@example.com')
    await user.type(screen.getByLabelText(/^Password/), 'Password123!')
    await user.click(screen.getByRole('button', { name: 'Sign up' }))

    await user.type(await screen.findByLabelText('Verification code'), '123456')
    await user.click(screen.getByRole('button', { name: 'Verify' }))
    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
  })

  it('sends Visitors on protected pages to log in', async () => {
    renderWithProviders(<App />, { route: '/me/bookings' })
    expect(await screen.findByRole('heading', { name: 'Log in' })).toBeInTheDocument()
  })

  it('blocks Attendees from the Organizer dashboard', async () => {
    window.localStorage.setItem('localbini.fakeAuth', JSON.stringify(users.attendee))
    renderWithProviders(<App />, { route: '/organizer', preloadedState: signedIn(users.attendee) })
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Not allowed' })).toBeInTheDocument())
  })
})
