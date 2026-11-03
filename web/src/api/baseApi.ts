import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'
import { authAdapter } from '../auth'
import { config } from '../config'

/**
 * RTK Query base API: every request carries the Cognito ID token when signed in.
 * Feature endpoints are injected with `baseApi.injectEndpoints` next to their pages.
 */
export const baseApi = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({
    baseUrl: config.apiUrl,
    prepareHeaders: async (headers) => {
      const token = await authAdapter.idToken().catch(() => null)
      if (token) headers.set('Authorization', `Bearer ${token}`)
      return headers
    },
  }),
  tagTypes: ['Event', 'MyEvents', 'Booking', 'Users'],
  endpoints: () => ({}),
})
