import { Link } from 'react-router-dom'
import type { EventDto } from './eventsApi'
import { formatDistance, formatPrice, formatWhen } from './format'

export function CoverPicture({ event, className }: { event: EventDto; className?: string }) {
  return event.cover_picture_url ? (
    <img className={className ?? 'cover'} src={event.cover_picture_url} alt={`Cover picture of ${event.title}`} loading="lazy" />
  ) : (
    <div className={`${className ?? 'cover'} cover-placeholder`} aria-hidden="true">
      {event.title.slice(0, 1)}
    </div>
  )
}

export function EventCard({ event }: { event: EventDto }) {
  const distance = formatDistance(event.distance_km)
  return (
    <li className="event-card">
      <Link to={`/events/${event.id}`} aria-label={event.title}>
        <CoverPicture event={event} />
        <div className="event-card-body">
          <h2>{event.title}</h2>
          <p className="muted">{formatWhen(event.starts_at)}</p>
          <p>
            {event.location.name}, {event.location.city}
            {distance && <span className="muted"> · {distance}</span>}
          </p>
          <p className="price">{formatPrice(event.price_cents, event.currency)}</p>
        </div>
      </Link>
    </li>
  )
}
