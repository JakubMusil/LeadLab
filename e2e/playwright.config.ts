import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright configuration for LeadLab end-to-end tests.
 *
 * Tests run against a locally started development server.  In CI the server
 * is started automatically via `webServer`.
 *
 * Environment variables:
 *   BASE_URL        — override the default http://localhost:8000 target.
 *   CI              — set by GitHub Actions; enables retries and stricter timeouts.
 */
export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [
    ['html', { outputFolder: 'playwright-report', open: 'never' }],
    ['list'],
  ],
  use: {
    baseURL: process.env.BASE_URL ?? 'http://localhost:8000',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    // Persist authentication state between tests within the same worker.
    storageState: './auth-state.json',
  },

  projects: [
    // Setup project — logs in and saves auth state.
    {
      name: 'setup',
      testMatch: '**/auth.setup.ts',
      use: { storageState: undefined },
    },
    // Main test suite — runs authenticated.
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
      dependencies: ['setup'],
    },
    {
      name: 'mobile-chrome',
      use: { ...devices['Pixel 7'] },
      dependencies: ['setup'],
    },
  ],
})
