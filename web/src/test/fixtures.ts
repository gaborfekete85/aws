import type { EventDto } from '../features/events/eventsApi'

export function anEvent(overrides: Partial<EventDto> = {}): EventDto {
  return {
    id: 'evt-1',
    organizer_id: 'org-1',
    title: 'Sunset jazz on the lake',
    description: 'Live quartet by the water.',
    important_information: 'Bring a blanket.\nNo dogs.',
    cover_picture_key: 'covers/evt-1/a.jpg',
    cover_picture_url: 'https://cdn.example.net/covers/evt-1/a.jpg',
    starts_at: '2031-06-01T16:00:00+00:00',
    ends_at: '2031-06-01T18:00:00+00:00',
    places: 40,
    price_cents: 2500,
    currency: 'CHF',
    is_free: false,
    status: 'published',
    location: { name: 'Seebad Enge', address: 'Mythenquai 9', city: 'Zürich', lat: 47.3617, lng: 8.5367 },
    distance_km: 1.234,
    ...overrides,
  }
}

export function aPage(items: EventDto[], extra: Partial<{ count: number; offset: number; next_offset: number | null }> = {}) {
  return { items, count: items.length, limit: 20, offset: 0, next_offset: null, ...extra }
}
