import { screen } from '@testing-library/react'
import { renderWithProviders, signedIn, users } from '../test/render'
import { NavBar } from './NavBar'

const links = () => screen.getAllByRole('link').map((a) => a.textContent)

describe('NavBar is role-aware', () => {
  it('Visitor: search, log in, sign up', () => {
    renderWithProviders(<NavBar />, { preloadedState: signedIn(null) })
    expect(links()).toEqual(['Localbini', 'Find Events', 'Log in', 'Sign up'])
  })

  it('Attendee: adds My Bookings and log out', () => {
    renderWithProviders(<NavBar />, { preloadedState: signedIn(users.attendee) })
    expect(links()).toEqual(['Localbini', 'Find Events', 'My Bookings'])
    expect(screen.getByRole('button', { name: 'Log out' })).toBeInTheDocument()
    expect(screen.getByTestId('signed-in-as')).toHaveTextContent('Ada')
  })

  it('Organizer: adds the dashboard', () => {
    renderWithProviders(<NavBar />, { preloadedState: signedIn(users.organizer) })
    expect(links()).toEqual(['Localbini', 'Find Events', 'My Bookings', 'Organizer'])
  })

  it('Admin: sees Organizer and Admin', () => {
    renderWithProviders(<NavBar />, { preloadedState: signedIn(users.admin) })
    expect(links()).toEqual(['Localbini', 'Find Events', 'My Bookings', 'Organizer', 'Admin'])
  })
})
