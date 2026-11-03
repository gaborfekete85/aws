import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { aPage, anEvent } from '../../test/fixtures'
import { mockFetch } from '../../test/fetchMock'
import { renderWithProviders } from '../../test/render'
import { EventCard } from './EventCard'
import { EventDetailPage } from './EventDetailPage'
import { formatDistance, formatPrice, formatWhen } from './format'
import { SearchPage } from './SearchPage'

afterEach(() => vi.unstubAllGlobals())

describe('format helpers', () => {
  it('formats Zürich time, prices and distances', () => {
    expect(formatWhen('2031-06-01T16:00:00+00:00')).toBe('Sun, 1 Jun 2031, 18:00')
    expect(formatPrice(0, 'CHF')).toBe('Free')
    expect(formatPrice(2500, 'CHF')).toMatch(/CHF\s?25\.00/)
    expect(formatDistance(0.45)).toBe('450 m away')
    expect(formatDistance(12.34)).toBe('12.3 km away')
    expect(formatDistance(null)).toBeNull()
  })
})

describe('EventCard', () => {
  it('shows Cover picture, title, date, Location, distance and price', () => {
    renderWithProviders(
      <ul>
        <EventCard event={anEvent()} />
      </ul>,
    )
    expect(screen.getByRole('img', { name: 'Cover picture of Sunset jazz on the lake' })).toHaveAttribute(
      'src',
      'https://cdn.example.net/covers/evt-1/a.jpg',
    )
    expect(screen.getByRole('link', { name: 'Sunset jazz on the lake' })).toHaveAttribute('href', '/events/evt-1')
    expect(screen.getByText(/Seebad Enge, Zürich/)).toBeInTheDocument()
    expect(screen.getByText(/1\.2 km away/)).toBeInTheDocument()
  })

  it('falls back to a placeholder without a Cover picture', () => {
    renderWithProviders(
      <ul>
        <EventCard event={anEvent({ cover_picture_url: null, price_cents: 0 })} />
      </ul>,
    )
    expect(screen.queryByRole('img')).toBeNull()
    expect(screen.getByText('Free')).toBeInTheDocument()
  })
})

describe('SearchPage', () => {
  it('geocodes the place and searches near it with the date range', async () => {
    const { calls } = mockFetch({
      'GET /search': () => [{ lat: '47.3769', lon: '8.5417', display_name: 'Zürich, Switzerland' }],
      'GET /events': ({ url }) =>
        url.searchParams.get('lat') ? aPage([anEvent()]) : aPage([]),
    })
    const user = userEvent.setup()
    renderWithProviders(<SearchPage />)

    await user.type(screen.getByLabelText('Place'), 'Zürich')
    await user.selectOptions(screen.getByLabelText('Within'), '10')
    await user.clear(screen.getByLabelText('From'))
    await user.type(screen.getByLabelText('From'), '2031-06-01')
    await user.type(screen.getByLabelText('To'), '2031-06-30')
    await user.click(screen.getByRole('button', { name: 'Search' }))

    expect(await screen.findByRole('link', { name: 'Sunset jazz on the lake' })).toBeInTheDocument()
    expect(screen.getByText(/1 Event found near Zürich/)).toBeInTheDocument()
    const search = calls.filter((c) => c.path === '/events').at(-1)!
    const params = new URLSearchParams(search.search)
    expect(Object.fromEntries(params)).toMatchObject({
      lat: '47.3769',
      lng: '8.5417',
      radius_km: '10',
      from: '2031-06-01',
      to: '2031-06-30',
    })
  })

  it('tells the Visitor when a place is unknown', async () => {
    mockFetch({ 'GET /search': () => [], 'GET /events': () => aPage([]) })
    const user = userEvent.setup()
    renderWithProviders(<SearchPage />)
    await user.type(screen.getByLabelText('Place'), 'Atlantis')
    await user.click(screen.getByRole('button', { name: 'Search' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('We could not find "Atlantis".')
  })

  it('uses the browser location', async () => {
    const { calls } = mockFetch({ 'GET /events': () => aPage([anEvent()]) })
    vi.stubGlobal('navigator', {
      ...navigator,
      geolocation: {
        getCurrentPosition: (ok: PositionCallback) =>
          ok({ coords: { latitude: 46.948, longitude: 7.4474 } } as GeolocationPosition),
      },
    })
    const user = userEvent.setup()
    renderWithProviders(<SearchPage />)
    await user.click(screen.getByRole('button', { name: 'Use my location' }))
    await waitFor(() => expect(calls.some((c) => c.search.includes('lat=46.948'))).toBe(true))
  })

  it('pages through results', async () => {
    const { calls } = mockFetch({
      'GET /events': ({ url }) =>
        url.searchParams.get('offset') === '20'
          ? aPage([anEvent({ id: 'evt-21', title: 'Page two' })], { count: 21, offset: 20 })
          : aPage([anEvent()], { count: 21, next_offset: 20 }),
    })
    const user = userEvent.setup()
    renderWithProviders(<SearchPage />)
    await user.click(await screen.findByRole('button', { name: 'Next' }))
    expect(await screen.findByRole('link', { name: 'Page two' })).toBeInTheDocument()
    expect(calls.some((c) => c.search.includes('offset=20'))).toBe(true)
  })
})

describe('EventDetailPage', () => {
  function renderDetail(id = 'evt-1') {
    return renderWithProviders(
      <Routes>
        <Route path="/events/:eventId" element={<EventDetailPage />} />
      </Routes>,
      { route: `/events/${id}` },
    )
  }

  it('shows description, Important information, Location, date, price and places left', async () => {
    mockFetch({
      'GET /events/evt-1': () => anEvent(),
      'GET /events/evt-1/availability': () => ({
        event_id: 'evt-1', places_total: 40, places_left: 12, price_cents: 2500, currency: 'CHF', open: true,
      }),
    })
    renderDetail()
    expect(await screen.findByRole('heading', { name: 'Sunset jazz on the lake' })).toBeInTheDocument()
    expect(screen.getByText('Live quartet by the water.')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Important information' })).toBeInTheDocument()
    expect(screen.getByText(/Bring a blanket\./)).toBeInTheDocument()
    expect(screen.getByText(/Mythenquai 9, Zürich/)).toBeInTheDocument()
    expect(screen.getByText(/Sun, 1 Jun 2031, 18:00/)).toBeInTheDocument()
    expect(await screen.findByTestId('places-left')).toHaveTextContent('12 of 40')
  })

  it('says sold out', async () => {
    mockFetch({
      'GET /events/evt-1': () => anEvent(),
      'GET /events/evt-1/availability': () => ({
        event_id: 'evt-1', places_total: 40, places_left: 0, price_cents: 2500, currency: 'CHF', open: true,
      }),
    })
    renderDetail()
    expect(await screen.findByTestId('places-left')).toHaveTextContent('Sold out')
  })

  it('flags a cancelled Event and does not ask for availability', async () => {
    const { calls } = mockFetch({ 'GET /events/evt-1': () => anEvent({ status: 'cancelled' }) })
    renderDetail()
    expect(await screen.findByRole('status')).toHaveTextContent('This Event has been cancelled.')
    expect(calls.some((c) => c.path.endsWith('/availability'))).toBe(false)
  })

  it('shows not found for unknown Events', async () => {
    mockFetch({})
    renderDetail('nope')
    expect(await screen.findByRole('heading', { name: 'Event not found' })).toBeInTheDocument()
  })
})
