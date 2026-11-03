import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { makeStore, type RootState } from '../app/store'
import { createFakeAdapter } from '../auth/fakeAdapter'
import type { AuthAdapter, AuthUser } from '../auth/types'

export const users: Record<'attendee' | 'organizer' | 'admin', AuthUser> = {
  attendee: { sub: 'u1', email: 'ada@example.com', name: 'Ada', groups: [] },
  organizer: { sub: 'u2', email: 'olga@example.com', name: 'Olga', groups: ['organizer'] },
  admin: { sub: 'u3', email: 'adam@example.com', name: 'Adam', groups: ['admin'] },
}

export function signedIn(user: AuthUser | null): Partial<RootState> {
  return {
    auth: {
      status: user ? 'signedIn' : 'signedOut',
      user,
      error: null,
      pendingConfirmationFor: null,
    },
  }
}

export function renderWithProviders(
  ui: ReactElement,
  {
    route = '/',
    preloadedState,
    auth = createFakeAdapter(),
  }: { route?: string; preloadedState?: Partial<RootState>; auth?: AuthAdapter } = {},
) {
  const store = makeStore({ preloadedState, auth })
  return {
    store,
    ...render(
      <Provider store={store}>
        <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
      </Provider>,
    ),
  }
}
