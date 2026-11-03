import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright UI tests (own package so they can run against any deployment).
 * - Offline (default): builds the app with VITE_AUTH_MODE=fake and serves it with `vite preview`.
 * - Against a deployment: E2E_BASE_URL=https://main.xxxx.amplifyapp.com (plus E2E_* credentials).
 */
const baseURL = process.env.E2E_BASE_URL ?? 'http://localhost:4173'
const offline = !process.env.E2E_BASE_URL

export default defineConfig({
  testDir: '.',
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [['list'], ['html', { open: 'never' }]] : 'list',
  use: {
    baseURL,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  grepInvert: offline ? /@dev/ : undefined,
  webServer: offline
    ? {
        command: 'cd ../../web && bun run build:fake && bun run preview --port 4173 --strictPort',
        url: 'http://localhost:4173',
        reuseExistingServer: !process.env.CI,
        timeout: 120_000,
      }
    : undefined,
})
