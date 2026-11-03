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
  timeout: offline ? 30_000 : 90_000,
  reporter: process.env.CI
    ? [['list'], ['html', { open: 'never' }], ['junit', { outputFile: 'test-results/junit.xml' }]]
    : 'list',
  use: {
    baseURL,
    // deployed runs keep full evidence for the CI artifact; offline runs only on failure
    trace: offline ? 'retain-on-failure' : 'on',
    screenshot: offline ? 'only-on-failure' : 'on',
    video: offline ? 'off' : 'retain-on-failure',
  },
  outputDir: 'test-results',
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
