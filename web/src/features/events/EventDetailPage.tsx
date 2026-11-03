import type { ReactNode } from 'react'
import { Link, useParams } from 'react-router-dom'
import { CoverPicture } from './EventCard'
import { useGetAvailabilityQuery, useGetEventQuery } from './eventsApi'
import { formatPrice, formatWhen } from './format'

/** Description, Important information, Location, date, price and places left. */
export function EventDetailPage({ bookingPanel }: { bookingPanel?: ReactNode }) {
  const { eventId = '' } = useParams()
  const { data: event, isLoading, error } = useGetEventQuery(eventId)
  const { data: availability } = useGetAvailabilityQuery(eventId, { skip: !event || event.status !== 'published' })

  if (isLoading) return <p className="muted">Loading…</p>
  if (error || !event) {
    return (
      <section>
        <h1>Event not found</h1>
        <p>
          <Link to="/">Back to search</Link>
        </p>
      </section>
    )
  }

  const mapUrl = `https://www.openstreetmap.org/?mlat=${event.location.lat}&mlon=${event.location.lng}#map=16/${event.location.lat}/${event.location.lng}`

  return (
    <article className="event-detail">
      <CoverPicture event={event} className="cover-large" />
      {event.status === 'cancelled' && (
        <p role="status" className="banner error">
          This Event has been cancelled.
        </p>
      )}
      <h1>{event.title}</h1>
      <dl className="facts">
        <dt>When</dt>
        <dd>
          {formatWhen(event.starts_at)} – {formatWhen(event.ends_at)}
        </dd>
        <dt>Where</dt>
        <dd>
          {event.location.name}, {event.location.address}, {event.location.city}{' '}
          <a href={mapUrl} target="_blank" rel="noreferrer">
            Map
          </a>
        </dd>
        <dt>Price</dt>
        <dd>{formatPrice(event.price_cents, event.currency)} per place</dd>
        {availability && (
          <>
            <dt>Places left</dt>
            <dd data-testid="places-left">
              {availability.places_left > 0 ? `${availability.places_left} of ${availability.places_total}` : 'Sold out'}
            </dd>
          </>
        )}
      </dl>
      {event.status === 'published' && bookingPanel}
      {event.description && (
        <section>
          <h2>About</h2>
          <p className="prewrap">{event.description}</p>
        </section>
      )}
      {event.important_information && (
        <section className="callout">
          <h2>Important information</h2>
          <p className="prewrap">{event.important_information}</p>
        </section>
      )}
    </article>
  )
}
