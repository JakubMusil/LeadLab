/**
 * Critical path E2E test: Record lifecycle
 *
 * Covers:
 *   1. Navigate to Records list
 *   2. Create a new record
 *   3. Change record status via inline badge editor
 *   4. Open record detail and add a comment activity
 *   5. Create a task on the record
 *   6. Complete the task
 */
import { test, expect } from '@playwright/test'

test.describe('Record lifecycle', () => {
  const recordTitle = `E2E Record ${Date.now()}`

  test('create a record', async ({ page }) => {
    await page.goto('/app/records')
    await expect(page.getByRole('heading', { name: /records/i })).toBeVisible()

    // Open create modal.
    await page.getByRole('button', { name: /new record/i }).click()
    await page.getByLabel(/title/i).fill(recordTitle)
    await page.getByRole('button', { name: /create/i }).click()

    // The new record should appear in the list.
    await expect(page.getByText(recordTitle)).toBeVisible({ timeout: 10_000 })
  })

  test('change record status', async ({ page }) => {
    await page.goto('/app/records')

    // Find our lead and click the status badge.
    const row = page.locator('tr, [data-testid="record-row"]').filter({ hasText: recordTitle }).first()
    await expect(row).toBeVisible({ timeout: 10_000 })

    const statusBadge = row.locator('[data-testid="status-badge"], .status-badge').first()
    await statusBadge.click()

    // Select "Contacted" from the dropdown.
    await page.getByRole('option', { name: /contacted/i }).click()

    // Verify the badge now shows "contacted".
    await expect(row.getByText(/contacted/i)).toBeVisible({ timeout: 5_000 })
  })

  test('add a comment activity on record detail', async ({ page }) => {
    await page.goto('/app/records')

    // Navigate to lead detail.
    await page.getByText(recordTitle).first().click()
    await page.waitForURL(/\/app\/records\//)

    // Switch to Activities tab if not already visible.
    const activitiesTab = page.getByRole('tab', { name: /activit/i })
    if (await activitiesTab.isVisible()) {
      await activitiesTab.click()
    }

    const commentInput = page.getByPlaceholder(/add a comment|write a comment/i)
    await commentInput.fill('This is an automated E2E test comment.')

    await page.getByRole('button', { name: /post|submit|add/i }).first().click()

    await expect(page.getByText('This is an automated E2E test comment.')).toBeVisible({
      timeout: 10_000,
    })
  })

  test('create and complete a task on the record', async ({ page }) => {
    await page.goto('/app/records')
    await page.getByText(recordTitle).first().click()
    await page.waitForURL(/\/app\/records\//)

    // Switch to Tasks tab.
    const tasksTab = page.getByRole('tab', { name: /tasks/i })
    if (await tasksTab.isVisible()) {
      await tasksTab.click()
    }

    // Create task.
    const taskTitle = `E2E Task ${Date.now()}`
    const taskInput = page.getByPlaceholder(/task title|new task/i)
    await taskInput.fill(taskTitle)
    await page.getByRole('button', { name: /add task|create task/i }).first().click()

    // The task should appear.
    await expect(page.getByText(taskTitle)).toBeVisible({ timeout: 10_000 })

    // Complete the task by clicking the checkbox/complete button next to it.
    const taskRow = page.locator('li, [data-testid="task-row"]').filter({ hasText: taskTitle }).first()
    const completeBtn = taskRow.getByRole('checkbox').or(taskRow.getByRole('button', { name: /complete/i })).first()
    await completeBtn.click()

    // The task should be marked done (e.g. strikethrough or checked state).
    await expect(taskRow).toHaveClass(/completed|done|line-through/, { timeout: 5_000 }).catch(() => {
      // Alternative: just confirm the task checkbox is now checked.
      return expect(completeBtn).toBeChecked({ timeout: 5_000 })
    })
  })
})
