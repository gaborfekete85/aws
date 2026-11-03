import { expect, test, type Page } from '@playwright/test'
import { OFFLINE_API, json, offline } from './fixtures'

/** A stateful stand-in for the Catalog API + S3, so the journey behaves like the real thing. */
async function mockCatalogBackend(page: Page) {
  const events = new Map<string, Record<string, unknown>>()
  let uploaded: string | null = null

  await page.route('https://nominatim.openstreetmap.org/**', (route) =>
    json(route, [{ lat: '47.3769', lon: '8.5417', display_name: 'Zürich' }]),
  )
  await page.route('https://media.example.test/**', async (route) => {
    const headers = route.request().headers()
    expect(headers['content-type']).toBe('image/png')
    uploaded = new URL(route.request().url()).pathname.slice(1)
    await route.fulfill({ status: 200 })
  })
  await page.route(`${OFFLINE_API}/**`, async (route) => {
    const request = route.request()
    const url = new URL(request.url())
    const method = request.method()
    const path = url.pathname
    const body = request.postDataJSON?.() ?? null
    const id = path.split('/')[2]

    if (method === 'POST' && path === '/events') {
      const event = {
        ...body,
        id: 'evt-new',
        organizer_id: 'fake-organizer@example.com',
        status: 'draft',
        is_free: body.price_cents === 0,
        cover_picture_key: null,
        cover_picture_url: null,
        location: { ...body.location, lat: 47.3769, lng: 8.5417 },
        updated_at: new Date().toISOString(),
      }
      events.set(event.id, event)
      return json(route, event, 201)
    }
    if (method === 'GET' && path === '/organizer/events') return json(route, { items: [...events.values()] })
    if (method === 'GET' && path.startsWith('/organizer/events/')) return json(route, events.get(path.split('/')[3]))
    if (method === 'POST' && path.endsWith('/cover-picture/upload-url')) {
      return json(route, {
        key: `covers/${id}/cover.png`,
        upload_url: `https://media.example.test/covers/${id}/cover.png?X-Amz-Signature=sig`,
        method: 'PUT',
        headers: { 'Content-Type': body.content_type, 'Content-Length': String(body.content_length) },
        expires_in: 300,
        max_bytes: 5242880,
      }, 201)
    }
    if (method === 'PUT' && path.endsWith('/cover-picture')) {
      expect(uploaded).toBe(body.key) // attach only after the S3 upload
      const event = { ...events.get(id)!, cover_picture_key: body.key, cover_picture_url: `https://cdn.example.test/${body.key}`, updated_at: new Date().toISOString() }
      events.set(id, event)
      return json(route, event)
    }
    if (method === 'POST' && path.endsWith('/publish')) {
      const event = { ...events.get(id)!, status: 'published', updated_at: new Date().toISOString() }
      events.set(id, event)
      return json(route, event)
    }
    if (method === 'GET' && path === '/events') {
      const published = [...events.values()].filter((e) => e.status === 'published')
      return json(route, { items: published, count: published.length, limit: 20, offset: 0, next_offset: null })
    }
    if (method === 'GET' && path.startsWith('/events/')) return json(route, events.get(id))
    return json(route, { message: `unmocked ${method} ${path}` }, 404)
  })
  await page.route('https://cdn.example.test/**', (route) =>
    route.fulfill({ status: 200, contentType: 'image/png', body: PNG }),
  )
}

// 1x1 transparent PNG
const PNG = Buffer.from(
  'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==',
  'base64',
)

test.describe('Organizer dashboard', () => {
  test.skip(!offline, 'offline flow; the deployed journey lives in journeys.spec.ts')

  test('create → upload Cover picture → publish → visible in search', async ({ page }) => {
    await mockCatalogBackend(page)

    await page.goto('/login')
    await page.getByLabel('Email').fill('organizer@example.com')
    await page.getByLabel('Password').fill('Password123!')
    await page.getByRole('button', { name: 'Log in' }).click()
    await page.getByRole('link', { name: 'Organizer' }).click()
    await expect(page.getByText('No Events here yet.')).toBeVisible()

    // create
    await page.getByRole('link', { name: 'New Event' }).click()
    await page.getByLabel('Title').fill('Rooftop salsa night')
    await page.getByLabel('Important information').fill('Comfortable shoes recommended.')
    await page.getByLabel('Starts').fill('2031-07-04T19:00')
    await page.getByLabel('Ends').fill('2031-07-04T23:00')
    await page.getByLabel('Places').fill('60')
    await page.getByLabel('Price per place').fill('18')
    await page.getByLabel('Location name').fill('Frau Gerolds Garten')
    await page.getByLabel('Address').fill('Geroldstrasse 23')
    await page.getByLabel('City').fill('Zürich')
    await page.getByRole('button', { name: 'Create draft' }).click()
    await expect(page.getByRole('heading', { name: /Rooftop salsa night/ })).toContainText('draft')

    // upload cover
    await page.getByLabel('Upload a Cover picture').setInputFiles({ name: 'cover.png', mimeType: 'image/png', buffer: PNG })
    await expect(page.getByText('Cover picture updated.')).toBeVisible()
    await expect(page.getByRole('img', { name: 'Cover picture of Rooftop salsa night' })).toBeVisible()

    // publish (with confirmation)
    await page.getByRole('link', { name: '← My Events' }).click()
    await page.getByRole('button', { name: 'Publish' }).click()
    await page.getByRole('dialog').getByRole('button', { name: 'Publish' }).click()
    await expect(page.getByRole('button', { name: 'Cancel Event' })).toBeVisible()

    // visible in search
    await page.getByRole('link', { name: 'Find Events' }).click()
    await page.getByLabel('Place').fill('Zürich')
    await page.getByRole('button', { name: 'Search' }).click()
    await expect(page.getByRole('link', { name: 'Rooftop salsa night' })).toBeVisible()
  })
})
