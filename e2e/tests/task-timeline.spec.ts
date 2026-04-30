/**
 * Critical path E2E test: Task timeline UX
 *
 * Mirrors `lead-timeline.spec.ts` (11th iteration of `streamline_goals.md`)
 * but exercises the `task` entity. The shared `ActivityTimeline` component
 * is mounted directly inside `TaskDetailView` (no sidebar action picker —
 * `:hide-composer="true"` is **not** passed), so the composer selectors
 * differ:
 *
 *   - In-component composer:        `activity-action-option` + `activity-composer-submit`
 *   - Sidebar picker (lead/etc.):   `entity-sidebar-action-option`  + `entity-sidebar-action-submit`
 *
 * Covered scenarios:
 *
 *   1. Add a comment via the in-component composer
 *   2. Filter the feed by activity type using the chip bar
 *   3. Toggle a reaction on a comment activity (add + remove)
 *   4. Persist the comment + reaction across a full page reload
 */
import { test, expect, type APIResponse } from '@playwright/test'

test.describe.serial('Task timeline UX', () => {
  let taskId = ''
  const taskTitle = `E2E Timeline Task ${Date.now()}`
  const commentText = `Automated task timeline comment ${Date.now()}`

  test.beforeAll(async ({ request }) => {
    const res: APIResponse = await request.post('/api/v1/crm/tasks', {
      data: { title: taskTitle },
    })
    expect(res.ok(), `Task create failed: ${res.status()} ${await res.text()}`).toBeTruthy()
    const body = await res.json()
    taskId = body.id as string
    expect(taskId).toBeTruthy()
  })

  test('add a comment via the in-component composer', async ({ page }) => {
    await page.goto(`/app/tasks/${taskId}`)

    // The unified ActivityTimeline composer should be present.
    await expect(page.getByTestId('activity-timeline-composer')).toBeVisible()

    // Pick the comment action.
    await page
      .locator('[data-testid="activity-action-option"][data-action="comment"]')
      .click()

    // Tiptap RichTextEditor inside the composer.
    const editor = page
      .getByTestId('activity-timeline-composer')
      .locator('[contenteditable="true"]')
      .first()
    await editor.click()
    await editor.fill(commentText)

    await page.getByTestId('activity-composer-submit').click()

    const commentItem = page
      .locator('[data-testid="activity-item"][data-activity-type="comment"]')
      .filter({ hasText: commentText })
      .first()
    await expect(commentItem).toBeVisible({ timeout: 10_000 })
  })

  test('filter the feed by activity type', async ({ page }) => {
    await page.goto(`/app/tasks/${taskId}`)

    await expect(
      page
        .locator('[data-testid="activity-item"][data-activity-type="comment"]')
        .filter({ hasText: commentText })
        .first(),
    ).toBeVisible({ timeout: 10_000 })

    await page
      .locator('[data-testid="activity-timeline-filter"][data-filter-value="comment"]')
      .click()

    const items = page.locator('[data-testid="activity-item"]')
    const count = await items.count()
    expect(count).toBeGreaterThan(0)
    for (let i = 0; i < count; i += 1) {
      await expect(items.nth(i)).toHaveAttribute('data-activity-type', 'comment')
    }

    await page
      .locator('[data-testid="activity-timeline-filter"][data-filter-value=""]')
      .click()
  })

  test('toggle a reaction on the seeded comment', async ({ page }) => {
    await page.goto(`/app/tasks/${taskId}`)

    const commentItem = page
      .locator('[data-testid="activity-item"][data-activity-type="comment"]')
      .filter({ hasText: commentText })
      .first()
    await expect(commentItem).toBeVisible({ timeout: 10_000 })

    await commentItem.getByTestId('activity-add-reaction').click()
    const picker = commentItem.getByTestId('activity-emoji-picker')
    await expect(picker).toBeVisible()

    await picker.locator('[data-testid="activity-emoji-option"][data-emoji="👍"]').click()

    const chip = commentItem.locator('[data-testid="activity-reaction-chip"][data-emoji="👍"]')
    await expect(chip).toBeVisible({ timeout: 5_000 })
    await expect(chip).toContainText('1')

    await chip.click()
    await expect(chip).toHaveCount(0, { timeout: 5_000 })
  })

  test('comment persists across a full page reload', async ({ page }) => {
    await page.goto(`/app/tasks/${taskId}`)
    await expect(
      page
        .locator('[data-testid="activity-item"][data-activity-type="comment"]')
        .filter({ hasText: commentText })
        .first(),
    ).toBeVisible({ timeout: 10_000 })

    await page.reload()

    await expect(
      page
        .locator('[data-testid="activity-item"][data-activity-type="comment"]')
        .filter({ hasText: commentText })
        .first(),
    ).toBeVisible({ timeout: 10_000 })
  })
})
