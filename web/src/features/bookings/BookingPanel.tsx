import { useState, type FormEvent } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAppDispatch, useAppSelector } from '../../app/hooks'
import type { Availability } from '../events/eventsApi'
import { formatPrice } from '../events/format'
import { apiErrorMessage } from '../organizer/organizerApi'
import { browser, useRequestBookingMutation } from './bookingsApi'
import { waitForCheckoutUrl } from './checkout'

const MAX_PER_BOOKING = 10

/** Choose places → Hold → Stripe Checkout (or instant confirmation for free Events). */
export function BookingPanel({ eventId, availability }: { eventId: string; availability?: Availability }) {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const location = useLocation()
  const user = useAppSelector((s) => s.auth.user)
  const [places, setPlaces] = useState(1)
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [requestBooking] = useRequestBookingMutation()

  if (!availability) return null
  if (!availability.open) return null
  if (availability.places_left <= 0) return <p className="card">Sold out.</p>
  if (!user) {
    return (
      <p className="card">
        <Link to="/login" state={{ from: location.pathname }}>
          Log in to book
        </Link>
      </p>
    )
  }

  const maxPlaces = Math.min(MAX_PER_BOOKING, availability.places_left)
  const free = availability.price_cents === 0
  const total = availability.price_cents * places

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setError(null)
    setBusy('Reserving your places…')
    const result = await requestBooking({ eventId, places })
    if ('error' in result) {
      setBusy(null)
      setError(apiErrorMessage(result.error))
      return
    }
    const booking = result.data
    if (booking.status === 'confirmed') {
      navigate(`/checkout/success?booking_id=${booking.booking_id}`)
      return
    }
    try {
      setBusy('Opening secure payment…')
      browser.redirect(await waitForCheckoutUrl(dispatch, booking.booking_id))
    } catch (err) {
      setBusy(null)
      setError(err instanceof Error ? err.message : 'Could not start Checkout.')
    }
  }

  return (
    <form className="card booking-panel" onSubmit={onSubmit} aria-label="Book">
      <label>
        Places
        <select value={places} onChange={(e) => setPlaces(Number(e.target.value))}>
          {Array.from({ length: maxPlaces }, (_, i) => i + 1).map((n) => (
            <option key={n} value={n}>
              {n}
            </option>
          ))}
        </select>
      </label>
      <p className="price" data-testid="booking-total">
        {free ? 'Free' : `Total ${formatPrice(total, availability.currency)}`}
      </p>
      <button type="submit" disabled={busy !== null}>
        {busy ?? (free ? 'Book for free' : 'Book and pay')}
      </button>
      {!free && <p className="muted small">Places are held for 15 minutes while you pay.</p>}
      {error && (
        <p role="alert" className="error">
          {error}
        </p>
      )}
    </form>
  )
}
