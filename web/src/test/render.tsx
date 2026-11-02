import { render } from '@testing-library/react'
import type { ReactElement } from 'react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { makeStore, type RootState } from '../app/store'

export function renderWithProviders(
  ui: ReactElement,
  { route = '/', preloadedState }: { route?: string; preloadedState?: Partial<RootState> } = {},
) {
  const store = makeStore(preloadedState)
  return {
    store,
    ...render(
      <Provider store={store}>
        <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
      </Provider>,
    ),
  }
}
