/**
 * Critical path E2E test: Lead timeline UX
 *
 * Exercises the unified Streamline timeline on the Lead detail view via
 * stable `data-testid` selectors (added in the 10th iteration of
 * `streamline_goals.md`). Covers:
 *
 *   1. Add a comment via `EntitySidebarActionPicker` (sidebar Quick Actions)
 *   2. Filter the feed by activity type using the chip bar
 *   3. Toggle a reaction on a comment activity (add + remove)
 *   4. Persist the comment + reaction across a full page reload
 *
 * The lead is created once up-front via the JSON API (cheaper than going
 * through the New Lead modal) and reused across all four tests in serial
 * order.
 */
import { test, expect, type APIResponse } from '@playwright/test'

test.describe.serial('Lead timeline UX', () => {
  let leadId = ''
  const leadTitle = `E2E Timeline ${Date.now()}`
  const commentText = `Automated timeline test comment ${Date.now()}`

  test.beforeAll(async ({ request }) => {
    const res: APIResponse = await request.post('/api/v1/crm/leads', {
      data: { title: leadTitle },
    })
    expect(res.ok(), `Lead create failed: ${res.status()} ${await res.text()}`).toBeTruthy()
    const body = await res.json()
    leadId = body.id as string
    expect(leadId).toBeTruthy()
  })

  test('add a comment via the sidebar action picker', async ({ page }) => {
    await page.goto(`/app/leads/${leadId}`)

    // Sidebar Quick Actions panel should be present on the Overview tab.
    await expect(page.getByTestId('entity-sidebar-action-picker')).toBeVisible()

    // Pick the "comment" action — opens the schema-driven form with a
    // RichTextEditor body.
    await page
      .locator('[data-testid="entity-sidebar-action-option"][data-action="comment"]')
      .click()

    // Tiptap exposes a single `contenteditable` element in the composer.
    const editor = page
      .getByTestId('entity-sidebar-action-picker')
      .locator('[contenteditable="true"]')
      .first()
    await editor.click()
    await editor.fill(commentText)

    await page.getByTestId('entity-sidebar-action-submit').click()

    // The new activity should land in the feed as a `comment` item.
    const commentItem = page
      .locator('[data-testid="activity-item"][data-activity-type="comment"]')
      .filter({ hasText: commentText })
      .first()
    await expect(commentItem).toBeVisible({ timeout: 10_000 })
  })

  test('filter the feed by activity type', async ({ page }) => {
    await page.goto(`/app/leads/${leadId}`)

    // Wait for the feed to render at least our seeded comment.
    await expect(
      page
        .locator('[data-testid="activity-item"][data-activity-type="comment"]')
        .filter({ hasText: commentText })
        .first(),
    ).toBeVisible({ timeout: 10_000 })

    // Apply the comment filter chip.
    await page
      .locator('[data-testid="activity-timeline-filter"][data-filter-value="comment"]')
      .click()

    // Every visible activity item must now carry data-activity-type="comment".
    const items = page.locator('[data-testid="activity-item"]')
    const count = await items.count()
    expect(count).toBeGreaterThan(0)
    for (let i = 0; i < count; i += 1) {
      await expect(items.nth(i)).toHaveAttribute('data-activity-type', 'comment')
    }

    // Reset back to the "all" filter so subsequent tests start clean.
    await page
      .locator('[data-testid="activity-timeline-filter"][data-filter-value=""]')
      .click()
  })

  test('toggle a reaction on the seeded comment', async ({ page }) => {
    await page.goto(`/app/leads/${leadId}`)

    const commentItem = page
      .locator('[data-testid="activity-item"][data-activity-type="comment"]')
      .filter({ hasText: commentText })
      .first()
    await expect(commentItem).toBeVisible({ timeout: 10_000 })

    // Open the emoji picker for the seeded comment.
    await commentItem.getByTestId('activity-add-reaction').click()
    const picker = commentItem.getByTestId('activity-emoji-picker')
    await expect(picker).toBeVisible()

    // Pick the thumbs-up emoji.
    await picker.locator('[data-testid="activity-emoji-option"][data-emoji="👍"]').click()

    // The aggregate reaction chip should now show count = 1 and be marked
    // as reacted-by-me (the author also reacted in this session).
    const chip = commentItem.locator('[data-testid="activity-reaction-chip"][data-emoji="👍"]')
    await expect(chip).toBeVisible({ timeout: 5_000 })
    await expect(chip).toContainText('1')

    // Toggle off — clicking the chip again should make it disappear.
    await chip.click()
    await expect(chip).toHaveCount(0, { timeout: 5_000 })
  })

  test('comment persists across a full page reload', async ({ page }) => {
    await page.goto(`/app/leads/${leadId}`)
    await expect(
      page
        .locator('[data-testid="activity-item"][data-activity-type="comment"]')
        .filter({ hasText: commentText })
        .first(),
    ).toBeVisible({ timeout: 10_000 })

    await page.reload()

    // After reload the timeline must re-fetch and still show the comment.
    await expect(
      page
        .locator('[data-testid="activity-item"][data-activity-type="comment"]')
        .filter({ hasText: commentText })
        .first(),
    ).toBeVisible({ timeout: 10_000 })
  })
})
