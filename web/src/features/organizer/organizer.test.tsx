import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { anEvent } from '../../test/fixtures'
import { mockFetch } from '../../test/fetchMock'
import { renderWithProviders, signedIn, users } from '../../test/render'
import { DashboardPage } from './DashboardPage'
import { changedFields, fromLocalInput, toInput, EMPTY } from './eventForm'
import { EventFormPage } from './EventFormPage'

afterEach(() => vi.unstubAllGlobals())

const organizer = { preloadedState: signedIn(users.organizer) }

describe('event form helpers', () => {
  it('converts the price to cents and datetimes to aware ISO', () => {
    const input = toInput({
      ...EMPTY,
      title: ' Jazz ',
      price: '25.50',
      places: '40',
      starts_at: '2031-06-01T18:00',
      ends_at: '2031-06-01T20:00',
      location_name: 'Seebad Enge',
      address: 'Mythenquai 9',
      city: 'Zürich',
    })
    expect(input.title).toBe('Jazz')
    expect(input.price_cents).toBe(2550)
    expect(input.places).toBe(40)
    expect(input.starts_at).toMatch(/Z$/)
    expect(new Date(input.starts_at).getTime()).toBe(new Date('2031-06-01T18:00').getTime())
  })

  it('patches only changed fields', () => {
    const before = toInput({ ...EMPTY, starts_at: '2031-06-01T18:00', ends_at: '2031-06-01T20:00' })
    const after = { ...before, places: 99 }
    expect(changedFields(before, after)).toEqual({ places: 99 })
    expect(fromLocalInput('2031-06-01T18:00')).toMatch(/^2031-06-01T/)
  })
})

describe('DashboardPage', () => {
  it('lists my Events and filters by status', async () => {
    const { calls } = mockFetch({
      'GET /organizer/events': ({ url }) =>
        url.searchParams.get('status') === 'draft'
          ? { items: [anEvent({ id: 'd1', title: 'Draft one', status: 'draft' })] }
          : {
              items: [
                anEvent({ id: 'd1', title: 'Draft one', status: 'draft' }),
                anEvent({ id: 'p1', title: 'Live one', status: 'published' }),
              ],
            },
    })
    const user = userEvent.setup()
    renderWithProviders(<DashboardPage />, organizer)

    expect(await screen.findByRole('link', { name: 'Live one' })).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: 'Drafts' }))
    await waitFor(() => expect(screen.queryByRole('link', { name: 'Live one' })).toBeNull())
    expect(calls.some((c) => c.search === '?status=draft')).toBe(true)
  })

  it('publishes only after confirmation', async () => {
    let status = 'draft'
    const { calls } = mockFetch({
      'GET /organizer/events': () => ({ items: [anEvent({ id: 'd1', title: 'Draft one', status: status as 'draft' })] }),
      'POST /events/d1/publish': () => {
        status = 'published'
        return anEvent({ id: 'd1', status: 'published' })
      },
    })
    const user = userEvent.setup()
    renderWithProviders(<DashboardPage />, organizer)

    await user.click(await screen.findByRole('button', { name: 'Publish' }))
    const dialog = screen.getByRole('dialog', { name: 'Publish "Draft one"?' })
    await user.click(within(dialog).getByRole('button', { name: 'Publish' }))

    expect(await screen.findByRole('button', { name: 'Cancel Event' })).toBeInTheDocument()
    expect(calls.filter((c) => c.method === 'POST')).toHaveLength(1)
  })

  it('does not cancel when the Organizer keeps the Event', async () => {
    const { calls } = mockFetch({
      'GET /organizer/events': () => ({ items: [anEvent({ id: 'p1', title: 'Live one' })] }),
    })
    const user = userEvent.setup()
    renderWithProviders(<DashboardPage />, organizer)
    await user.click(await screen.findByRole('button', { name: 'Cancel Event' }))
    const dialog = screen.getByRole('dialog', { name: 'Cancel "Live one"?' })
    expect(dialog).toHaveTextContent('every Attendee is emailed')
    await user.click(within(dialog).getByRole('button', { name: 'Keep it' }))
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })
})

describe('EventFormPage', () => {
  function renderForm(route: string) {
    return renderWithProviders(
      <Routes>
        <Route path="/organizer/events/new" element={<EventFormPage />} />
        <Route path="/organizer/events/:eventId" element={<EventFormPage />} />
      </Routes>,
      { ...organizer, route },
    )
  }

  it('creates a Draft and opens it for editing', async () => {
    let body: unknown
    mockFetch({
      'POST /events': ({ body: b }) => {
        body = b
        return anEvent({ id: 'new-1', title: 'Jazz', status: 'draft' })
      },
      'GET /organizer/events/new-1': () => anEvent({ id: 'new-1', title: 'Jazz', status: 'draft' }),
    })
    const user = userEvent.setup()
    renderForm('/organizer/events/new')

    await user.type(screen.getByLabelText('Title'), 'Jazz')
    await user.type(screen.getByLabelText('Starts'), '2031-06-01T18:00')
    await user.type(screen.getByLabelText('Ends'), '2031-06-01T20:00')
    await user.clear(screen.getByLabelText('Price per place'))
    await user.type(screen.getByLabelText('Price per place'), '25')
    await user.type(screen.getByLabelText('Location name'), 'Seebad Enge')
    await user.type(screen.getByLabelText('Address'), 'Mythenquai 9')
    await user.type(screen.getByLabelText('City'), 'Zürich')
    await user.click(screen.getByRole('button', { name: 'Create draft' }))

    expect(await screen.findByLabelText('Upload a Cover picture')).toBeInTheDocument()
    expect(body).toMatchObject({
      title: 'Jazz',
      price_cents: 2500,
      currency: 'CHF',
      location: { name: 'Seebad Enge', address: 'Mythenquai 9', city: 'Zürich' },
    })
  })

  it('rejects an end before the start without calling the API', async () => {
    const { calls } = mockFetch({})
    const user = userEvent.setup()
    renderForm('/organizer/events/new')
    await user.type(screen.getByLabelText('Title'), 'X')
    await user.type(screen.getByLabelText('Starts'), '2031-06-01T20:00')
    await user.type(screen.getByLabelText('Ends'), '2031-06-01T18:00')
    for (const label of ['Location name', 'Address', 'City']) await user.type(screen.getByLabelText(label), 'x')
    await user.click(screen.getByRole('button', { name: 'Create draft' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('must end after it starts')
    expect(calls).toHaveLength(0)
  })

  it('uploads the Cover picture: ticket, direct PUT to S3, attach', async () => {
    let cover: string | null = null
    const { calls } = mockFetch({
      'GET /organizer/events/evt-1': () => anEvent({ cover_picture_url: cover }),
      'POST /events/evt-1/cover-picture/upload-url': ({ body }) => {
        expect(body).toEqual({ content_type: 'image/png', content_length: 4 })
        return {
          key: 'covers/evt-1/x.png',
          upload_url: 'https://media.s3.amazonaws.com/covers/evt-1/x.png?X-Amz-Signature=abc',
          method: 'PUT',
          headers: { 'Content-Type': 'image/png', 'Content-Length': '4' },
          expires_in: 300,
          max_bytes: 5242880,
        }
      },
      'PUT /covers/evt-1/x.png': () => new Response(null, { status: 200 }),
      'PUT /events/evt-1/cover-picture': () => {
        cover = 'https://cdn.example.net/covers/evt-1/x.png'
        return anEvent({ cover_picture_url: cover })
      },
    })
    const user = userEvent.setup()
    renderForm('/organizer/events/evt-1')

    const file = new File([new Uint8Array([1, 2, 3, 4])], 'cover.png', { type: 'image/png' })
    await user.upload(await screen.findByLabelText('Upload a Cover picture'), file)

    await waitFor(() => expect(screen.queryByRole('alert')?.textContent ?? screen.queryByRole('status')?.textContent).toBe('Cover picture updated.'))
    const s3 = calls.find((c) => c.path === '/covers/evt-1/x.png')
    expect(s3?.method).toBe('PUT')
    expect(calls.findIndex((c) => c.path === '/events/evt-1/cover-picture')).toBeGreaterThan(calls.indexOf(s3!))
  })

  it('refuses non-images and files over 5 MB before uploading', async () => {
    const { calls } = mockFetch({ 'GET /organizer/events/evt-1': () => anEvent() })
    const user = userEvent.setup({ applyAccept: false })
    renderForm('/organizer/events/evt-1')
    const input = await screen.findByLabelText('Upload a Cover picture')

    await user.upload(input, new File(['%PDF'], 'doc.pdf', { type: 'application/pdf' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('JPEG, PNG or WebP')

    const big = new File([new Uint8Array(5 * 1024 * 1024 + 1)], 'big.jpg', { type: 'image/jpeg' })
    await user.upload(input, big)
    expect(await screen.findByRole('alert')).toHaveTextContent('at most 5 MB')
    expect(calls.some((c) => c.method === 'POST')).toBe(false)
  })

  it('edits only the changed fields', async () => {
    let patch: unknown
    mockFetch({
      'GET /organizer/events/evt-1': () => anEvent(),
      'PATCH /events/evt-1': ({ body }) => {
        patch = body
        return anEvent({ places: 55 })
      },
    })
    const user = userEvent.setup()
    renderForm('/organizer/events/evt-1')
    const places = await screen.findByLabelText('Places')
    await user.clear(places)
    await user.type(places, '55')
    await user.click(screen.getByRole('button', { name: 'Save changes' }))
    await waitFor(() => expect(patch).toEqual({ places: 55 }))
  })
})
