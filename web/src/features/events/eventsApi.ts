import { baseApi } from '../../api/baseApi'

export interface EventLocation {
  name: string
  address: string
  city: string
  lat: number
  lng: number
}

export type EventStatus = 'draft' | 'published' | 'cancelled'

export interface EventDto {
  id: string
  organizer_id: string
  title: string
  description: string
  important_information: string
  cover_picture_key: string | null
  cover_picture_url: string | null
  starts_at: string
  ends_at: string
  places: number
  price_cents: number
  currency: string
  is_free: boolean
  status: EventStatus
  location: EventLocation
  created_at?: string
  updated_at?: string
  published_at?: string | null
  cancelled_at?: string | null
  distance_km?: number | null
}

export interface SearchParams {
  lat?: number
  lng?: number
  radius_km?: number
  from?: string
  to?: string
  limit?: number
  offset?: number
}

export interface SearchPage {
  items: EventDto[]
  count: number
  limit: number
  offset: number
  next_offset: number | null
}

export interface Availability {
  event_id: string
  places_total: number
  places_left: number
  price_cents: number
  currency: string
  open: boolean
}

function clean(params: SearchParams): Record<string, string | number> {
  return Object.fromEntries(
    Object.entries(params).filter(([, v]) => v !== undefined && v !== ''),
  ) as Record<string, string | number>
}

export const eventsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    searchEvents: build.query<SearchPage, SearchParams>({
      query: (params) => ({ url: '/events', params: clean(params) }),
      providesTags: (page) =>
        page ? page.items.map((e) => ({ type: 'Event' as const, id: e.id })) : ['Event'],
    }),
    getEvent: build.query<EventDto, string>({
      query: (id) => `/events/${encodeURIComponent(id)}`,
      providesTags: (_r, _e, id) => [{ type: 'Event', id }],
    }),
    getAvailability: build.query<Availability, string>({
      query: (id) => `/events/${encodeURIComponent(id)}/availability`,
      providesTags: (_r, _e, id) => [{ type: 'Booking', id }],
    }),
  }),
})

export const { useSearchEventsQuery, useGetEventQuery, useGetAvailabilityQuery } = eventsApi
