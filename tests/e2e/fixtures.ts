import type { Page, Route } from '@playwright/test'

/** Offline runs: the fake build calls this API base; deployed runs hit the real API. */
export const OFFLINE_API = 'http://localhost:4010'
export const offline = !process.env.E2E_BASE_URL

export const jazz = {
  id: 'evt-jazz',
  organizer_id: 'org-1',
  title: 'Sunset jazz on the lake',
  description: 'Live quartet by the water.',
  important_information: 'Bring a blanket.',
  cover_picture_key: null,
  cover_picture_url: null,
  starts_at: '2031-06-01T16:00:00+00:00',
  ends_at: '2031-06-01T18:00:00+00:00',
  places: 40,
  price_cents: 2500,
  currency: 'CHF',
  is_free: false,
  status: 'published',
  location: { name: 'Seebad Enge', address: 'Mythenquai 9', city: 'Zürich', lat: 47.3617, lng: 8.5367 },
  distance_km: 1.6,
}

export const json = (route: Route, body: unknown, status = 200) =>
  route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })

/** Serve a tiny in-memory catalog + availability for offline UI tests. */
export async function mockCatalog(page: Page, events = [jazz], placesLeft = 12) {
  await page.route('https://nominatim.openstreetmap.org/**', (route) =>
    json(route, [{ lat: '47.3769', lon: '8.5417', display_name: 'Zürich, Switzerland' }]),
  )
  await page.route(`${OFFLINE_API}/events?**`, (route) =>
    json(route, { items: events, count: events.length, limit: 20, offset: 0, next_offset: null }),
  )
  for (const event of events) {
    await page.route(`${OFFLINE_API}/events/${event.id}`, (route) => json(route, event))
    await page.route(`${OFFLINE_API}/events/${event.id}/availability`, (route) =>
      json(route, {
        event_id: event.id,
        places_total: event.places,
        places_left: placesLeft,
        price_cents: event.price_cents,
        currency: event.currency,
        open: true,
      }),
    )
  }
}
