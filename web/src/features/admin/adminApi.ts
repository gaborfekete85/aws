import { baseApi } from '../../api/baseApi'

export interface AdminUser {
  username: string
  sub: string
  email: string
  name: string
  enabled: boolean
  status: string
  roles: ('admin' | 'organizer')[]
}

export interface UsersPage {
  items: AdminUser[]
  next_token: string | null
}

export const adminApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    listUsers: build.query<UsersPage, { search?: string; next?: string }>({
      query: ({ search, next }) => ({
        url: '/admin/users',
        params: { ...(search ? { search } : {}), ...(next ? { next } : {}) },
      }),
      providesTags: ['Users'],
    }),
    setOrganizer: build.mutation<AdminUser, { username: string; organizer: boolean }>({
      query: ({ username, organizer }) => ({
        url: `/admin/users/${encodeURIComponent(username)}/roles/organizer`,
        method: organizer ? 'PUT' : 'DELETE',
      }),
      invalidatesTags: ['Users'],
    }),
  }),
})

export const { useListUsersQuery, useSetOrganizerMutation } = adminApi
