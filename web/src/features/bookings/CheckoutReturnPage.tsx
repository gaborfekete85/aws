import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { FINAL_STATUSES, useGetBookingQuery, type BookingStatus } from './bookingsApi'

const POLL_MS = 1500
const GIVE_UP_AFTER_MS = 60_000

const MESSAGES: Record<BookingStatus, { title: string; body: string }> = {
  pending: { title: 'Confirming your payment…', body: 'This usually takes a few seconds.' },
  confirmed: { title: "You're booked!", body: 'A confirmation email is on its way.' },
  expired: {
    title: 'Your Hold expired',
    body: 'The places were released before the payment arrived. You have not been charged unless Stripe confirmed it; if so, we will contact you.',
  },
  cancelled: { title: 'Booking cancelled', body: 'This Event was cancelled.' },
  needs_attention: {
    title: 'We are looking into your Booking',
    body: 'Your payment arrived after the Hold expired. Our team will contact you.',
  },
}

/** Stripe redirects back here; the webhook confirms asynchronously, so poll the Booking. */
export function CheckoutReturnPage({ outcome }: { outcome: 'success' | 'cancel' }) {
  const [params] = useSearchParams()
  const bookingId = params.get('booking_id') ?? ''
  const [gaveUp, setGaveUp] = useState(false)
  const [settled, setSettled] = useState(false)
  // Poll while the webhook has not settled the Booking yet (derived, not synced via effects).
  const { data, error } = useGetBookingQuery(bookingId, {
    skip: !bookingId,
    pollingInterval: outcome === 'success' && !settled && !gaveUp ? POLL_MS : 0,
  })
  const isFinal = !!data && FINAL_STATUSES.includes(data.status)
  if (isFinal && !settled) setSettled(true) // adjust state during render (React docs pattern)

  useEffect(() => {
    if (outcome !== 'success' || settled) return
    const id = setTimeout(() => setGaveUp(true), GIVE_UP_AFTER_MS)
    return () => clearTimeout(id)
  }, [outcome, settled])

  if (!bookingId || error) {
    return (
      <section className="card narrow">
        <h1>Booking not found</h1>
        <Link to="/me/bookings">My Bookings</Link>
      </section>
    )
  }

  if (outcome === 'cancel' && data?.status === 'pending') {
    return (
      <section className="card narrow">
        <h1>Payment not completed</h1>
        <p>Your places stay on hold for a few minutes. You can finish paying from My Bookings.</p>
        <Link to="/me/bookings">My Bookings</Link>
      </section>
    )
  }

  const message = MESSAGES[data?.status ?? 'pending']
  return (
    <section className="card narrow" aria-live="polite">
      <h1>{gaveUp && data?.status === 'pending' ? 'Still waiting for the payment' : message.title}</h1>
      <p>{gaveUp && data?.status === 'pending' ? 'Check My Bookings in a minute.' : message.body}</p>
      {data && (
        <p className="muted">
          {data.event_title} · {data.places} place{data.places === 1 ? '' : 's'}
        </p>
      )}
      <Link to="/me/bookings">My Bookings</Link>
    </section>
  )
}
