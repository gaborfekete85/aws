import { useState, type FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { EventCard } from './EventCard'
import { useSearchEventsQuery, type SearchParams } from './eventsApi'
import { isoDay } from './format'
import { currentPosition, geocodePlace } from './geo'

const RADII = [5, 10, 25, 50, 100]

function num(value: string | null): number | undefined {
  return value === null || value === '' ? undefined : Number(value)
}

/** Search by place (geocoded or browser location) and date range. State lives in the URL. */
export function SearchPage() {
  const [params, setParams] = useSearchParams()
  const [place, setPlace] = useState(params.get('place') ?? '')
  const [from, setFrom] = useState(params.get('from') ?? isoDay(new Date()))
  const [to, setTo] = useState(params.get('to') ?? '')
  const [radius, setRadius] = useState(params.get('radius_km') ?? '25')
  const [locating, setLocating] = useState(false)
  const [placeError, setPlaceError] = useState<string | null>(null)

  const query: SearchParams = {
    lat: num(params.get('lat')),
    lng: num(params.get('lng')),
    radius_km: params.get('lat') ? num(params.get('radius_km')) ?? 25 : undefined,
    from: params.get('from') ?? undefined,
    to: params.get('to') ?? undefined,
    offset: num(params.get('offset')),
  }
  const { data, isFetching, error } = useSearchEventsQuery(query)

  function apply(coords: { lat: number; lng: number; label: string } | null, offset = 0) {
    const next = new URLSearchParams()
    if (coords) {
      next.set('lat', coords.lat.toFixed(5))
      next.set('lng', coords.lng.toFixed(5))
      next.set('place', coords.label)
      next.set('radius_km', radius)
    }
    if (from) next.set('from', from)
    if (to) next.set('to', to)
    if (offset) next.set('offset', String(offset))
    setParams(next)
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    setPlaceError(null)
    const text = place.trim()
    if (!text) return apply(null)
    if (text === params.get('place') && params.get('lat')) {
      return apply({ lat: Number(params.get('lat')), lng: Number(params.get('lng')), label: text })
    }
    try {
      const found = await geocodePlace(text)
      if (!found) {
        setPlaceError(`We could not find "${text}".`)
        return
      }
      apply({ ...found, label: text })
    } catch {
      setPlaceError('Place lookup is unavailable right now.')
    }
  }

  async function useMyLocation() {
    setPlaceError(null)
    setLocating(true)
    try {
      const here = await currentPosition()
      setPlace(here.label)
      apply(here)
    } catch (err) {
      setPlaceError(err instanceof Error ? err.message : 'Location unavailable')
    } finally {
      setLocating(false)
    }
  }

  return (
    <section>
      <h1>Find local Events</h1>
      <form className="search" onSubmit={onSubmit} role="search">
        <label className="grow">
          Place
          <input
            value={place}
            onChange={(e) => setPlace(e.target.value)}
            placeholder="Zürich, Bern, an address…"
          />
        </label>
        <label>
          Within
          <select value={radius} onChange={(e) => setRadius(e.target.value)}>
            {RADII.map((r) => (
              <option key={r} value={r}>
                {r} km
              </option>
            ))}
          </select>
        </label>
        <label>
          From
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </label>
        <label>
          To
          <input type="date" value={to} min={from} onChange={(e) => setTo(e.target.value)} />
        </label>
        <div className="search-actions">
          <button type="submit">Search</button>
          <button type="button" className="secondary" onClick={useMyLocation} disabled={locating}>
            {locating ? 'Locating…' : 'Use my location'}
          </button>
        </div>
      </form>
      {placeError && (
        <p role="alert" className="error">
          {placeError}
        </p>
      )}
      {error && (
        <p role="alert" className="error">
          Could not load Events.
        </p>
      )}

      <p className="muted" aria-live="polite">
        {isFetching ? 'Searching…' : data ? `${data.count} Event${data.count === 1 ? '' : 's'} found` : ''}
        {params.get('place') && !isFetching ? ` near ${params.get('place')}` : ''}
      </p>
      <ul className="event-grid" aria-label="Search results">
        {data?.items.map((event) => <EventCard key={event.id} event={event} />)}
      </ul>
      {data && (data.offset > 0 || data.next_offset !== null) && (
        <nav className="pager" aria-label="Pages">
          <button
            type="button"
            className="secondary"
            disabled={data.offset === 0}
            onClick={() => apply(currentCoords(params), Math.max(0, data.offset - data.limit))}
          >
            Previous
          </button>
          <button
            type="button"
            className="secondary"
            disabled={data.next_offset === null}
            onClick={() => apply(currentCoords(params), data.next_offset ?? 0)}
          >
            Next
          </button>
        </nav>
      )}
    </section>
  )
}

function currentCoords(params: URLSearchParams) {
  const lat = params.get('lat')
  const lng = params.get('lng')
  return lat && lng ? { lat: Number(lat), lng: Number(lng), label: params.get('place') ?? '' } : null
}
