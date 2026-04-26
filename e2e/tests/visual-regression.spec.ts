/**
 * Visual regression tests using Playwright's screenshot comparison.
 *
 * These tests capture screenshots of critical pages and diff them against
 * stored snapshots.  Run `npx playwright test --update-snapshots` to
 * regenerate baselines when intentional UI changes are made.
 *
 * Pages covered:
 *   - Dashboard overview
 *   - Lead detail (first lead in list)
 *   - Leads Kanban board view
 */
import { test, expect } from '@playwright/test'

test.describe('Visual regression', () => {
  test('dashboard overview matches snapshot', async ({ page }) => {
    await page.goto('/app/dashboard')
    // Wait for stat cards to load.
    await page.waitForLoadState('networkidle')
    // Mask dynamic numbers and timestamps so they don't cause false positives.
    await expect(page).toHaveScreenshot('dashboard.png', {
      mask: [
        page.locator('[data-testid="stat-value"]'),
        page.locator('.stat-number'),
        // Mask chart canvas (varies on every render).
        page.locator('canvas'),
      ],
      maxDiffPixelRatio: 0.03,
    })
  })

  test('leads kanban board matches snapshot', async ({ page }) => {
    await page.goto('/app/leads')
    await page.waitForLoadState('networkidle')

    // Switch to Kanban view if a toggle exists.
    const kanbanToggle = page.getByRole('button', { name: /kanban|board/i })
    if (await kanbanToggle.isVisible()) {
      await kanbanToggle.click()
      await page.waitForTimeout(500)
    }

    await expect(page).toHaveScreenshot('leads-kanban.png', {
      mask: [page.locator('canvas'), page.locator('[data-testid="lead-card-value"]')],
      maxDiffPixelRatio: 0.03,
    })
  })

  test('lead detail page matches snapshot', async ({ page }) => {
    await page.goto('/app/leads')
    await page.waitForLoadState('networkidle')

    // Click the first lead to open its detail page.
    const firstLead = page.locator('tr, [data-testid="lead-row"]').first()
    if (await firstLead.isVisible()) {
      await firstLead.click()
      await page.waitForURL(/\/app\/leads\//)
      await page.waitForLoadState('networkidle')

      await expect(page).toHaveScreenshot('lead-detail.png', {
        mask: [
          page.locator('canvas'),
          page.locator('time'),
          page.locator('[data-testid="activity-timestamp"]'),
        ],
        maxDiffPixelRatio: 0.03,
      })
    } else {
      test.skip(true, 'No leads available for screenshot comparison.')
    }
  })
})
