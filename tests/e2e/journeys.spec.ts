import { expect, test, type Browser, type Page } from '@playwright/test'

/**
 * Critical journeys against a deployed environment (runs after every dev deploy).
 *
 *   E2E_BASE_URL            web app URL (Amplify)
 *   E2E_ORGANIZER_EMAIL/PASSWORD   Cognito user in the organizer group
 *   E2E_USER_EMAIL/PASSWORD        plain Attendee
 *
 * Self-contained: the Organizer creates and publishes uniquely named Events,
 * the Attendee books them, and cleanup cancels them again.
 */
const RUN = process.env.GITHUB_RUN_ID ?? `${Date.now()}`
const FREE_TITLE = `E2E free ${RUN}`
const PAID_TITLE = `E2E paid ${RUN}`

const organizer = { email: process.env.E2E_ORGANIZER_EMAIL, password: process.env.E2E_ORGANIZER_PASSWORD }
const attendee = { email: process.env.E2E_USER_EMAIL, password: process.env.E2E_USER_PASSWORD }

test.describe.configure({ mode: 'serial' })
test.skip(!process.env.E2E_BASE_URL, 'deployed journeys need E2E_BASE_URL')
test.skip(!organizer.email || !attendee.email, 'needs E2E_ORGANIZER_* and E2E_USER_* credentials')

async function loginAs(browser: Browser, who: { email?: string; password?: string }): Promise<Page> {
  const page = await (await browser.newContext()).newPage()
  await page.goto('/login')
  await page.getByLabel('Email').fill(who.email!)
  await page.getByLabel('Password').fill(who.password!)
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page.getByTestId('signed-in-as')).toBeVisible({ timeout: 20_000 })
  return page
}

function nextWeek(hour: number): string {
  const d = new Date(Date.now() + 7 * 24 * 3600 * 1000)
  d.setHours(hour, 0, 0, 0)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:00`
}

async function createAndPublish(page: Page, title: string, price: string) {
  await page.goto('/organizer/events/new')
  await page.getByLabel('Title').fill(title)
  await page.getByLabel('Important information').fill('Created by the E2E suite.')
  await page.getByLabel('Starts').fill(nextWeek(18))
  await page.getByLabel('Ends').fill(nextWeek(20))
  await page.getByLabel('Places').fill('20')
  await page.getByLabel('Price per place').fill(price)
  await page.getByLabel('Location name').fill('Zürich HB')
  await page.getByLabel('Address').fill('Bahnhofplatz 1')
  await page.getByLabel('City').fill('Zürich')
  await page.getByRole('button', { name: 'Create draft' }).click()
  await expect(page.getByRole('heading', { name: new RegExp(title) })).toBeVisible({ timeout: 20_000 })

  await page.getByRole('link', { name: '← My Events' }).click()
  const row = page.getByRole('row', { name: new RegExp(title) })
  await row.getByRole('button', { name: 'Publish' }).click()
  await page.getByRole('dialog').getByRole('button', { name: 'Publish' }).click()
  await expect(row.getByRole('button', { name: 'Cancel Event' })).toBeVisible()
}

async function openFromSearch(page: Page, title: string) {
  await page.goto('/')
  await page.getByLabel('Place').fill('Zürich')
  await page.getByRole('button', { name: 'Search' }).click()
  // projection + search are eventually consistent: retry a few times
  await expect(async () => {
    await page.reload()
    await expect(page.getByRole('link', { name: title })).toBeVisible({ timeout: 3_000 })
  }).toPass({ timeout: 30_000 })
  await page.getByRole('link', { name: title }).click()
  await expect(page.getByRole('heading', { name: title })).toBeVisible()
}

test('login: real Cognito user/password @dev', async ({ browser }) => {
  const page = await loginAs(browser, attendee)
  await page.getByRole('button', { name: 'Log out' }).click()
  await expect(page.getByRole('link', { name: 'Log in' })).toBeVisible()
})

test('organizer creates and publishes Events @dev', async ({ browser }) => {
  const page = await loginAs(browser, organizer)
  await createAndPublish(page, FREE_TITLE, '0')
  await createAndPublish(page, PAID_TITLE, '12')
})

test('visitor finds the published Event in search @dev', async ({ page }) => {
  await openFromSearch(page, FREE_TITLE)
  await expect(page.getByText('Created by the E2E suite.')).toBeVisible()
})

test('attendee books a free Event @dev', async ({ browser }) => {
  const page = await loginAs(browser, attendee)
  await openFromSearch(page, FREE_TITLE)
  await page.getByRole('button', { name: 'Book for free' }).click()
  await expect(page.getByRole('heading', { name: "You're booked!" })).toBeVisible({ timeout: 30_000 })
})

test('attendee books a paid Event with a Stripe test card @dev', async ({ browser }) => {
  test.setTimeout(180_000)
  const page = await loginAs(browser, attendee)
  await openFromSearch(page, PAID_TITLE)
  await page.getByRole('button', { name: 'Book and pay' }).click()

  // Stripe-hosted Checkout (test mode)
  await page.waitForURL(/checkout\.stripe\.com/, { timeout: 30_000 })
  await page.getByLabel('Card number').fill('4242 4242 4242 4242')
  await page.getByLabel('Expiration').fill('12 / 34')
  await page.getByLabel('CVC').fill('123')
  await page.getByLabel(/Cardholder name|Name on card/).fill('Localbini E2E')
  const country = page.getByLabel(/Country or region/)
  if (await country.isVisible()) await country.selectOption('CH')
  await page.getByTestId('hosted-payment-submit-button').click()

  await page.waitForURL(/\/checkout\/success\?booking_id=/, { timeout: 60_000 })
  await expect(page.getByRole('heading', { name: "You're booked!" })).toBeVisible({ timeout: 60_000 })
  await page.getByRole('link', { name: 'My Bookings' }).first().click()
  await expect(page.getByRole('listitem').filter({ hasText: PAID_TITLE })).toContainText('Confirmed')
})

test.afterAll(async ({ browser }) => {
  // Cleanup: cancel what this run created (also exercises the cancellation path).
  const page = await loginAs(browser, organizer)
  await page.goto('/organizer')
  for (const title of [FREE_TITLE, PAID_TITLE]) {
    const row = page.getByRole('row', { name: new RegExp(title) })
    if (await row.getByRole('button', { name: 'Cancel Event' }).isVisible().catch(() => false)) {
      await row.getByRole('button', { name: 'Cancel Event' }).click()
      await page.getByRole('dialog').getByRole('button', { name: 'Cancel Event' }).click()
      await expect(row.getByText('cancelled')).toBeVisible()
    }
  }
})
