import { expect, test, type Page } from '@playwright/test'
import { OFFLINE_API, jazz, json, mockCatalog, offline } from './fixtures'

const FAKE_STRIPE = 'https://checkout.stripe.test'

async function login(page: Page, email: string, password: string) {
  await page.goto('/login')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page.getByTestId('signed-in-as')).toBeVisible()
}

/** Booking + Payments + a stand-in Stripe page that "pays" and redirects back. */
async function mockBookingBackend(page: Page, appOrigin: string) {
  let status = 'pending'
  let checkoutPolls = 0
  const booking = () => ({
    booking_id: 'b-1',
    event_id: jazz.id,
    event_title: jazz.title,
    places: 2,
    amount_cents: 5000,
    currency: 'CHF',
    status,
    created_at: new Date().toISOString(),
    hold_expires_at: new Date(Date.now() + 15 * 60_000).toISOString(),
    confirmed_at: null,
    cancelled_at: null,
  })
  await page.route(`${OFFLINE_API}/events/${jazz.id}/bookings`, (route) => json(route, booking(), 201))
  await page.route(`${OFFLINE_API}/bookings/b-1/checkout`, (route) =>
    ++checkoutPolls < 2
      ? json(route, { status: 'creating', retry_after_ms: 100 }, 202)
      : json(route, { status: 'open', url: `${FAKE_STRIPE}/pay/cs_test_1`, expires_at: null }),
  )
  await page.route(`${OFFLINE_API}/bookings/b-1`, (route) => json(route, booking()))
  await page.route(`${OFFLINE_API}/me/bookings`, (route) => json(route, { items: [booking()] }))
  await page.route(`${FAKE_STRIPE}/**`, (route) =>
    route.fulfill({
      contentType: 'text/html',
      body: `<html><body><h1>Stripe test checkout</h1>
        <button onclick="location.href='${appOrigin}/checkout/success?booking_id=b-1'">Pay CHF 50.00</button>
      </body></html>`,
    }),
  )
  // the webhook confirms the Booking a moment after Stripe redirects back
  return { confirmSoon: () => setTimeout(() => (status = 'confirmed'), 1500) }
}

test.describe('Checkout (offline)', () => {
  test.skip(!offline, 'mocked flow')

  test('Attendee books 2 places, pays on Stripe, sees confirmation and My Bookings', async ({ page, baseURL }) => {
    await mockCatalog(page)
    const backend = await mockBookingBackend(page, baseURL!)
    await login(page, 'ada@example.com', 'Password123!')

    await page.goto(`/events/${jazz.id}`)
    await page.getByLabel('Places').selectOption('2')
    await expect(page.getByTestId('booking-total')).toContainText('50.00')
    await page.getByRole('button', { name: 'Book and pay' }).click()

    await expect(page).toHaveURL(/checkout\.stripe\.test\/pay\/cs_test_1/)
    backend.confirmSoon()
    await page.getByRole('button', { name: 'Pay CHF 50.00' }).click()

    await expect(page.getByRole('heading', { name: 'Confirming your payment…' })).toBeVisible()
    await expect(page.getByRole('heading', { name: "You're booked!" })).toBeVisible({ timeout: 10_000 })

    await page.getByRole('link', { name: 'My Bookings' }).first().click()
    await expect(page.getByText('Confirmed')).toBeVisible()
  })
})
