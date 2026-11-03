import { baseApi } from '../../api/baseApi'

export type BookingStatus = 'pending' | 'confirmed' | 'cancelled' | 'expired' | 'needs_attention'

export interface Booking {
  booking_id: string
  event_id: string
  event_title: string
  places: number
  amount_cents: number
  currency: string
  status: BookingStatus
  created_at: string
  hold_expires_at: string | null
  confirmed_at: string | null
  cancelled_at: string | null
}

export type Checkout =
  | { status: 'creating'; retry_after_ms: number }
  | { status: 'open' | 'expired' | 'paid' | 'failed'; url: string | null; expires_at: string | null }

export const bookingsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    requestBooking: build.mutation<Booking, { eventId: string; places: number }>({
      query: ({ eventId, places }) => ({
        url: `/events/${encodeURIComponent(eventId)}/bookings`,
        method: 'POST',
        body: { places },
      }),
      invalidatesTags: (_r, _e, { eventId }) => [{ type: 'Booking', id: eventId }, 'Booking'],
    }),
    getBooking: build.query<Booking, string>({
      query: (id) => `/bookings/${encodeURIComponent(id)}`,
    }),
    myBookings: build.query<{ items: Booking[] }, void>({
      query: () => '/me/bookings',
      providesTags: ['Booking'],
    }),
    getCheckout: build.query<Checkout, string>({
      query: (bookingId) => `/bookings/${encodeURIComponent(bookingId)}/checkout`,
    }),
  }),
})

export const {
  useRequestBookingMutation,
  useGetBookingQuery,
  useMyBookingsQuery,
  useLazyGetCheckoutQuery,
} = bookingsApi

export const FINAL_STATUSES: BookingStatus[] = ['confirmed', 'cancelled', 'expired', 'needs_attention']

/** Indirection so tests can observe the redirect to Stripe. */
export const browser = {
  redirect(url: string) {
    window.location.assign(url)
  },
}
