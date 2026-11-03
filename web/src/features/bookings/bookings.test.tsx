import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { anEvent } from '../../test/fixtures'
import { mockFetch } from '../../test/fetchMock'
import { renderWithProviders, signedIn, users } from '../../test/render'
import { EventDetailPage } from '../events/EventDetailPage'
import { browser, type Booking } from './bookingsApi'
import { CheckoutReturnPage } from './CheckoutReturnPage'
import { MyBookingsPage } from './MyBookingsPage'

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function booking(overrides: Partial<Booking> = {}): Booking {
  return {
    booking_id: 'b-1',
    event_id: 'evt-1',
    event_title: 'Sunset jazz on the lake',
    places: 2,
    amount_cents: 5000,
    currency: 'CHF',
    status: 'pending',
    created_at: '2026-11-03T12:00:00+00:00',
    hold_expires_at: new Date(Date.now() + 10 * 60_000).toISOString(),
    confirmed_at: null,
    cancelled_at: null,
    ...overrides,
  }
}

const availability = (left = 12, price = 2500) => ({
  event_id: 'evt-1', places_total: 40, places_left: left, price_cents: price, currency: 'CHF', open: true,
})

function renderEventPage(user: typeof users.attendee | null = users.attendee) {
  if (user) window.localStorage.setItem('localbini.fakeAuth', JSON.stringify(user)) // fake session token
  return renderWithProviders(
    <Routes>
      <Route path="/events/:eventId" element={<EventDetailPage />} />
      <Route path="/checkout/success" element={<CheckoutReturnPage outcome="success" />} />
    </Routes>,
    { route: '/events/evt-1', preloadedState: signedIn(user) },
  )
}

describe('BookingPanel', () => {
  it('asks Visitors to log in', async () => {
    mockFetch({ 'GET /events/evt-1': () => anEvent(), 'GET /events/evt-1/availability': () => availability() })
    renderEventPage(null)
    expect(await screen.findByRole('link', { name: 'Log in to book' })).toBeInTheDocument()
  })

  it('offers at most the places left (and 10 per Booking)', async () => {
    mockFetch({ 'GET /events/evt-1': () => anEvent(), 'GET /events/evt-1/availability': () => availability(3) })
    renderEventPage()
    const select = await screen.findByLabelText('Places')
    expect(Array.from((select as HTMLSelectElement).options).map((o) => o.value)).toEqual(['1', '2', '3'])
  })

  it('paid Event: Hold, wait for the Checkout session, redirect to Stripe', async () => {
    let checkoutCalls = 0
    const redirect = vi.spyOn(browser, 'redirect').mockImplementation(() => {})
    const { calls } = mockFetch({
      'GET /events/evt-1': () => anEvent(),
      'GET /events/evt-1/availability': () => availability(),
      'POST /events/evt-1/bookings': ({ body }) => {
        expect(body).toEqual({ places: 2 })
        return booking()
      },
      'GET /bookings/b-1/checkout': () =>
        ++checkoutCalls < 2
          ? new Response(JSON.stringify({ status: 'creating', retry_after_ms: 10 }), {
              status: 202,
              headers: { 'Content-Type': 'application/json' },
            })
          : { status: 'open', url: 'https://checkout.stripe.com/c/pay/cs_test_1', expires_at: null },
    })
    const user = userEvent.setup()
    renderEventPage()

    await user.selectOptions(await screen.findByLabelText('Places'), '2')
    expect(screen.getByTestId('booking-total')).toHaveTextContent(/Total CHF\s?50\.00/)
    await user.click(screen.getByRole('button', { name: 'Book and pay' }))

    await waitFor(() => expect(redirect).toHaveBeenCalledWith('https://checkout.stripe.com/c/pay/cs_test_1'))
    expect(checkoutCalls).toBe(2)
    expect(calls.find((c) => c.method === 'POST')?.auth).toMatch(/^Bearer /)
  })

  it('free Event: confirmed immediately, no Stripe', async () => {
    const redirect = vi.spyOn(browser, 'redirect')
    mockFetch({
      'GET /events/evt-1': () => anEvent({ price_cents: 0, is_free: true }),
      'GET /events/evt-1/availability': () => availability(12, 0),
      'POST /events/evt-1/bookings': () => booking({ status: 'confirmed', amount_cents: 0, hold_expires_at: null }),
      'GET /bookings/b-1': () => booking({ status: 'confirmed' }),
    })
    const user = userEvent.setup()
    renderEventPage()
    await user.click(await screen.findByRole('button', { name: 'Book for free' }))
    expect(await screen.findByRole('heading', { name: "You're booked!" })).toBeInTheDocument()
    expect(redirect).not.toHaveBeenCalled()
  })

  it('shows the conflict when places ran out meanwhile', async () => {
    mockFetch({
      'GET /events/evt-1': () => anEvent(),
      'GET /events/evt-1/availability': () => availability(),
      'POST /events/evt-1/bookings': () =>
        new Response(JSON.stringify({ message: 'Only 1 place(s) left', places_left: 1 }), {
          status: 409,
          headers: { 'Content-Type': 'application/json' },
        }),
    })
    const user = userEvent.setup()
    renderEventPage()
    await user.click(await screen.findByRole('button', { name: 'Book and pay' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Only 1 place(s) left')
  })
})

describe('Checkout return pages', () => {
  it('success page polls until the webhook confirmed the Booking', async () => {
    let polls = 0
    mockFetch({
      'GET /bookings/b-1': () => (++polls < 3 ? booking() : booking({ status: 'confirmed' })),
    })
    renderWithProviders(<CheckoutReturnPage outcome="success" />, {
      route: '/checkout/success?booking_id=b-1',
      preloadedState: signedIn(users.attendee),
    })
    expect(await screen.findByRole('heading', { name: 'Confirming your payment…' })).toBeInTheDocument()
    expect(await screen.findByRole('heading', { name: "You're booked!" }, { timeout: 6000 })).toBeInTheDocument()
    expect(polls).toBeGreaterThanOrEqual(3)
  }, 10_000)

  it('explains an expired Hold', async () => {
    mockFetch({ 'GET /bookings/b-1': () => booking({ status: 'expired' }) })
    renderWithProviders(<CheckoutReturnPage outcome="success" />, {
      route: '/checkout/success?booking_id=b-1',
      preloadedState: signedIn(users.attendee),
    })
    expect(await screen.findByRole('heading', { name: 'Your Hold expired' })).toBeInTheDocument()
  })

  it('cancel page offers to finish later', async () => {
    mockFetch({ 'GET /bookings/b-1': () => booking() })
    renderWithProviders(<CheckoutReturnPage outcome="cancel" />, {
      route: '/checkout/cancel?booking_id=b-1',
      preloadedState: signedIn(users.attendee),
    })
    expect(await screen.findByRole('heading', { name: 'Payment not completed' })).toBeInTheDocument()
  })
})

describe('MyBookingsPage', () => {
  it('lists Bookings with status and resumes a pending payment', async () => {
    const redirect = vi.spyOn(browser, 'redirect').mockImplementation(() => {})
    mockFetch({
      'GET /me/bookings': () => ({
        items: [
          booking({ booking_id: 'b-1' }),
          booking({ booking_id: 'b-2', status: 'confirmed', event_title: 'Salsa night' }),
          booking({ booking_id: 'b-3', status: 'cancelled', event_title: 'Cancelled gig' }),
        ],
      }),
      'GET /bookings/b-1/checkout': () => ({ status: 'open', url: 'https://checkout.stripe.com/c/pay/cs_1', expires_at: null }),
    })
    const user = userEvent.setup()
    renderWithProviders(<MyBookingsPage />, { preloadedState: signedIn(users.attendee) })

    expect(await screen.findByText('Salsa night')).toBeInTheDocument()
    expect(screen.getByText('Confirmed')).toBeInTheDocument()
    expect(screen.getByText('Cancelled')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Complete payment' }))
    await waitFor(() => expect(redirect).toHaveBeenCalledWith('https://checkout.stripe.com/c/pay/cs_1'))
  })

  it('does not offer payment once the Hold expired', async () => {
    mockFetch({
      'GET /me/bookings': () => ({ items: [booking({ hold_expires_at: '2020-01-01T00:00:00+00:00' })] }),
    })
    renderWithProviders(<MyBookingsPage />, { preloadedState: signedIn(users.attendee) })
    expect(await screen.findByText('Awaiting payment')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Complete payment' })).toBeNull()
  })
})
