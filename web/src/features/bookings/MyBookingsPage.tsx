import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAppDispatch } from '../../app/hooks'
import { formatPrice, formatWhen } from '../events/format'
import { browser, useMyBookingsQuery, type Booking } from './bookingsApi'
import { waitForCheckoutUrl } from './checkout'

const LABELS: Record<Booking['status'], string> = {
  pending: 'Awaiting payment',
  confirmed: 'Confirmed',
  cancelled: 'Cancelled',
  expired: 'Expired',
  needs_attention: 'Under review',
}

function ResumePayment({ booking }: { booking: Booking }) {
  const dispatch = useAppDispatch()
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  if (booking.hold_expires_at && new Date(booking.hold_expires_at) < new Date()) return null

  async function resume() {
    setBusy(true)
    try {
      browser.redirect(await waitForCheckoutUrl(dispatch, booking.booking_id, { attempts: 3 }))
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Checkout unavailable')
      setBusy(false)
    }
  }

  return (
    <>
      <button type="button" onClick={resume} disabled={busy}>
        Complete payment
      </button>
      {error && <span className="error"> {error}</span>}
    </>
  )
}

export function MyBookingsPage() {
  const { data, isLoading, error } = useMyBookingsQuery()

  return (
    <section>
      <h1>My Bookings</h1>
      {isLoading && <p className="muted">Loading…</p>}
      {error && (
        <p role="alert" className="error">
          Could not load your Bookings.
        </p>
      )}
      {data && data.items.length === 0 && (
        <p className="muted">
          No Bookings yet. <Link to="/">Find an Event</Link>
        </p>
      )}
      <ul className="booking-list">
        {data?.items.map((booking) => (
          <li key={booking.booking_id} className="card">
            <div className="row">
              <Link to={`/events/${booking.event_id}`}>
                <strong>{booking.event_title || 'Event'}</strong>
              </Link>
              <span className={`badge badge-${booking.status}`}>{LABELS[booking.status]}</span>
            </div>
            <p className="muted">
              {booking.places} place{booking.places === 1 ? '' : 's'} ·{' '}
              {formatPrice(booking.amount_cents, booking.currency)} · booked {formatWhen(booking.created_at)}
            </p>
            {booking.status === 'pending' && <ResumePayment booking={booking} />}
          </li>
        ))}
      </ul>
    </section>
  )
}
