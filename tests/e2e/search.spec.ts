import { expect, test } from '@playwright/test'
import { mockCatalog, offline } from './fixtures'

test.describe('Event search', () => {
  test.skip(!offline, 'offline flow uses mocked data; see journeys.spec.ts for the deployed one')

  test('Visitor searches by place and dates, then opens an Event', async ({ page }) => {
    await mockCatalog(page)
    let searchUrl: URL | undefined
    page.on('request', (r) => {
      if (r.url().includes('/events?')) searchUrl = new URL(r.url())
    })

    await page.goto('/')
    await page.getByLabel('Place').fill('Zürich')
    await page.getByLabel('Within').selectOption('10')
    await page.getByLabel('From').fill('2031-06-01')
    await page.getByLabel('To').fill('2031-06-30')
    await page.getByRole('button', { name: 'Search' }).click()

    const result = page.getByRole('link', { name: 'Sunset jazz on the lake' })
    await expect(result).toBeVisible()
    await expect(page.getByText('1 Event found near Zürich')).toBeVisible()
    expect(Object.fromEntries(searchUrl!.searchParams)).toMatchObject({
      radius_km: '10',
      from: '2031-06-01',
      to: '2031-06-30',
    })
    await expect(page).toHaveURL(/lat=47\.37690.*place=Z/)

    await result.click()
    await expect(page.getByRole('heading', { name: 'Sunset jazz on the lake' })).toBeVisible()
    await expect(page.getByTestId('places-left')).toHaveText('12 of 40')
    await expect(page.getByText('Bring a blanket.')).toBeVisible()
  })

  test('search is shareable: reloading keeps the results', async ({ page }) => {
    await mockCatalog(page)
    await page.goto('/?lat=47.37690&lng=8.54170&place=Z%C3%BCrich&radius_km=10&from=2031-06-01')
    await expect(page.getByRole('link', { name: 'Sunset jazz on the lake' })).toBeVisible()
    await page.reload()
    await expect(page.getByRole('link', { name: 'Sunset jazz on the lake' })).toBeVisible()
  })
})
