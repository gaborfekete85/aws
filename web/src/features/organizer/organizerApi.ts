import { baseApi } from '../../api/baseApi'
import type { EventDto, EventStatus } from '../events/eventsApi'

export interface EventInput {
  title: string
  description: string
  important_information: string
  starts_at: string
  ends_at: string
  places: number
  price_cents: number
  currency: string
  location: { name: string; address: string; city: string }
}

export interface UploadTicket {
  key: string
  upload_url: string
  method: 'PUT'
  headers: Record<string, string>
  expires_in: number
  max_bytes: number
}

export const organizerApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listMyEvents: build.query<{ items: EventDto[] }, EventStatus | undefined>({
      query: (status) => ({ url: '/organizer/events', params: status ? { status } : {} }),
      providesTags: ['MyEvents'],
    }),
    getMyEvent: build.query<EventDto, string>({
      query: (id) => `/organizer/events/${encodeURIComponent(id)}`,
      providesTags: (_r, _e, id) => [{ type: 'Event', id }],
    }),
    createEvent: build.mutation<EventDto, EventInput>({
      query: (body) => ({ url: '/events', method: 'POST', body }),
      invalidatesTags: ['MyEvents'],
    }),
    updateEvent: build.mutation<EventDto, { id: string; changes: Partial<EventInput> }>({
      query: ({ id, changes }) => ({ url: `/events/${id}`, method: 'PATCH', body: changes }),
      invalidatesTags: (_r, _e, { id }) => ['MyEvents', { type: 'Event', id }],
    }),
    publishEvent: build.mutation<EventDto, string>({
      query: (id) => ({ url: `/events/${id}/publish`, method: 'POST' }),
      invalidatesTags: (_r, _e, id) => ['MyEvents', { type: 'Event', id }],
    }),
    cancelEvent: build.mutation<EventDto, string>({
      query: (id) => ({ url: `/events/${id}/cancel`, method: 'POST' }),
      invalidatesTags: (_r, _e, id) => ['MyEvents', { type: 'Event', id }],
    }),
    coverUploadUrl: build.mutation<UploadTicket, { id: string; content_type: string; content_length: number }>({
      query: ({ id, ...body }) => ({ url: `/events/${id}/cover-picture/upload-url`, method: 'POST', body }),
    }),
    attachCover: build.mutation<EventDto, { id: string; key: string }>({
      query: ({ id, key }) => ({ url: `/events/${id}/cover-picture`, method: 'PUT', body: { key } }),
      invalidatesTags: (_r, _e, { id }) => ['MyEvents', { type: 'Event', id }],
    }),
  }),
})

export const {
  useListMyEventsQuery,
  useGetMyEventQuery,
  useCreateEventMutation,
  useUpdateEventMutation,
  usePublishEventMutation,
  useCancelEventMutation,
  useCoverUploadUrlMutation,
  useAttachCoverMutation,
} = organizerApi

/** PUT the file straight to S3 with exactly the headers that were signed. */
export async function uploadToS3(ticket: UploadTicket, file: File): Promise<void> {
  const headers = { ...ticket.headers }
  delete headers['Content-Length'] // the browser sets it from the body; it must match the signed value
  const response = await fetch(ticket.upload_url, { method: 'PUT', headers, body: file })
  if (!response.ok) throw new Error(`Upload failed (${response.status})`)
}

export function apiErrorMessage(error: unknown): string {
  const data = (error as { data?: { message?: string; errors?: { msg: string; loc: string[] }[] } })?.data
  if (data?.errors?.length) return data.errors.map((e) => `${e.loc.join('.')}: ${e.msg}`).join('; ')
  return data?.message ?? 'Something went wrong'
}
