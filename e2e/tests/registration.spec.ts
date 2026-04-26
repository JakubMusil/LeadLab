/**
 * Critical path E2E test: Registration → Onboarding → Dashboard
 *
 * Uses a unique timestamp-based email to avoid conflicts with the shared
 * `auth.setup.ts` test account.
 */
import { test, expect } from '@playwright/test'

test.use({ storageState: undefined })

test('registration → onboarding → dashboard', async ({ page }) => {
  const ts = Date.now()
  const email = `e2e-reg-${ts}@leadlab.test`
  const password = 'TestPassword123!'

  // ── 1. Registration ──────────────────────────────────────────────────────
  await page.goto('/app/register')

  await page.getByLabel('First Name').fill('New')
  await page.getByLabel('Last Name').fill('User')
  await page.getByLabel('Email').fill(email)
  await page.getByLabel('Password').fill(password)
  await page.getByRole('button', { name: /sign up/i }).click()

  // ── 2. Onboarding ────────────────────────────────────────────────────────
  await page.waitForURL(/\/app\/onboarding/, { timeout: 15_000 })
  await expect(page.getByText(/get you set up|create.*workspace/i)).toBeVisible()

  await page.getByPlaceholder(/workspace name/i).fill(`Reg-Test-${ts}`)
  await page.getByRole('button', { name: /create workspace/i }).click()

  // ── 3. Dashboard ─────────────────────────────────────────────────────────
  await page.waitForURL(/\/app\/dashboard/, { timeout: 15_000 })
  await expect(page).toHaveTitle(/LeadLab/i)
  await expect(page.getByText(/dashboard/i).first()).toBeVisible()
})
