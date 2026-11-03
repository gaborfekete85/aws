import { createApi, fetchBaseQuery } from '@reduxjs/toolkit/query/react'
import type { AuthAdapter } from '../auth/types'
import { config } from '../config'

/**
 * RTK Query base API: every request carries the Cognito ID token when signed in.
 * The auth adapter comes from the store's thunk `extra` (dependency injection),
 * so tests and the fake mode use the same code path as production.
 * Feature endpoints are injected with `baseApi.injectEndpoints` next to their pages.
 */
export const baseApi = createApi({
  reducerPath: 'api',
  baseQuery: fetchBaseQuery({
    baseUrl: config.apiUrl,
    prepareHeaders: async (headers, { extra }) => {
      const { auth } = extra as { auth: AuthAdapter }
      const token = await auth.idToken().catch(() => null)
      if (token) headers.set('Authorization', `Bearer ${token}`)
      return headers
    },
  }),
  tagTypes: ['Event', 'MyEvents', 'Booking', 'Users'],
  endpoints: () => ({}),
})
