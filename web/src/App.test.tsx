import { screen } from '@testing-library/react'
import App from './App'
import { renderWithProviders } from './test/render'

describe('App', () => {
  it('renders the app name from the store', () => {
    renderWithProviders(<App />)
    expect(screen.getByRole('heading', { name: 'Localbini' })).toBeInTheDocument()
  })
})
