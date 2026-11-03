import { expect, test } from '@playwright/test'

/**
 * Login smoke test.
 * Offline it runs against the fake auth adapter; against a deployment (tagged @dev)
 * it uses a real Cognito test user from E2E_USER_EMAIL / E2E_USER_PASSWORD.
 */
test('Visitor logs in with email and password, sees their nav, and logs out', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('link', { name: 'Log in' })).toBeVisible()

  await page.getByRole('link', { name: 'Log in' }).click()
  await page.getByLabel('Email').fill('organizer@example.com')
  await page.getByLabel('Password').fill('Password123!')
  await page.getByRole('button', { name: 'Log in' }).click()

  await expect(page.getByTestId('signed-in-as')).toHaveText('organizer')
  await expect(page.getByRole('link', { name: 'Organizer' })).toBeVisible()
  await expect(page.getByRole('link', { name: 'Admin' })).toHaveCount(0)

  await page.getByRole('button', { name: 'Log out' }).click()
  await expect(page.getByRole('link', { name: 'Log in' })).toBeVisible()
})

test('wrong password shows an error', async ({ page }) => {
  await page.goto('/login')
  await page.getByLabel('Email').fill('ada@example.com')
  await page.getByLabel('Password').fill('not-the-password')
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page.getByRole('alert')).toContainText('Incorrect username or password')
})

test('real Cognito login @dev', async ({ page }) => {
  const email = process.env.E2E_USER_EMAIL
  const password = process.env.E2E_USER_PASSWORD
  test.skip(!email || !password, 'E2E_USER_EMAIL / E2E_USER_PASSWORD not set')
  await page.goto('/login')
  await page.getByLabel('Email').fill(email!)
  await page.getByLabel('Password').fill(password!)
  await page.getByRole('button', { name: 'Log in' }).click()
  await expect(page.getByTestId('signed-in-as')).toBeVisible()
})
