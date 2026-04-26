/**
 * Authentication setup — runs once before all other tests to create a
 * persisted browser storage state (cookies + localStorage) so that
 * subsequent tests start already logged in.
 *
 * The state is written to `./auth-state.json` which is referenced in
 * `playwright.config.ts` via `storageState`.
 */
import { test as setup, expect } from '@playwright/test'
import path from 'path'

const AUTH_FILE = path.join(__dirname, '..', 'auth-state.json')

const TEST_EMAIL = process.env.E2E_EMAIL ?? 'e2e@leadlab.test'
const TEST_PASSWORD = process.env.E2E_PASSWORD ?? 'TestPassword123!'

setup('authenticate', async ({ page }) => {
  await page.goto('/app/login')

  // Register the test user if they don't exist yet.
  const loginRes = await page.request.post('/api/v1/users/login', {
    data: { email: TEST_EMAIL, password: TEST_PASSWORD },
  })

  if (!loginRes.ok()) {
    // User doesn't exist — register first.
    await page.goto('/app/register')
    await page.getByLabel('First Name').fill('E2E')
    await page.getByLabel('Last Name').fill('Tester')
    await page.getByLabel('Email').fill(TEST_EMAIL)
    await page.getByLabel('Password').fill(TEST_PASSWORD)
    await page.getByRole('button', { name: /sign up/i }).click()
    await page.waitForURL(/\/app\/onboarding/)

    // Create workspace during onboarding.
    await page.getByPlaceholder(/workspace name/i).fill('E2E Workspace')
    await page.getByRole('button', { name: /create workspace/i }).click()
    await page.waitForURL(/\/app\/dashboard/)
  } else {
    // Log in via the UI.
    await page.goto('/app/login')
    await page.getByLabel('Email').fill(TEST_EMAIL)
    await page.getByLabel('Password').fill(TEST_PASSWORD)
    await page.getByRole('button', { name: /sign in/i }).click()
    await page.waitForURL(/\/app\/dashboard|\/app\/onboarding/)

    if (page.url().includes('/onboarding')) {
      await page.getByPlaceholder(/workspace name/i).fill('E2E Workspace')
      await page.getByRole('button', { name: /create workspace/i }).click()
      await page.waitForURL(/\/app\/dashboard/)
    }
  }

  await expect(page).toHaveURL(/\/app\/dashboard/)
  await page.context().storageState({ path: AUTH_FILE })
})
