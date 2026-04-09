import { test, expect } from '@playwright/test'

test.describe('Estimates', { tag: '@smoke' }, () => {
  test.setTimeout(30_000)

  test('renders page heading and filter controls', async ({ page }) => {
    await page.goto('/estimates')

    await expect(page.getByRole('heading', { name: 'Estimates' })).toBeVisible()

    // All five status filter buttons must be present
    for (const label of ['All', 'draft', 'reviewed', 'finalized', 'exported']) {
      await expect(page.getByRole('button', { name: label })).toBeVisible()
    }
  })

  test('status filter changes selection', async ({ page }) => {
    await page.goto('/estimates')

    // Wait for initial load to complete (subtitle changes from '...' to a count)
    await expect(page.locator('p').filter({ hasText: /estimate/ })).toBeVisible({ timeout: 10_000 })

    // Click the 'draft' filter
    await page.getByRole('button', { name: 'draft' }).click()

    // Subtitle should now include '· filtered by draft'
    await expect(
      page.locator('p').filter({ hasText: /filtered by draft/ })
    ).toBeVisible({ timeout: 10_000 })

    // Reset with 'All'
    await page.getByRole('button', { name: 'All' }).click()

    await expect(
      page.locator('p').filter({ hasText: /filtered by/ })
    ).not.toBeVisible()
  })

  test('view toggle renders table', async ({ page }) => {
    await page.goto('/estimates')

    // Default view is board — no table yet
    await expect(page.locator('table')).not.toBeVisible()

    // Switch to table view
    await page.getByRole('button', { name: 'Table' }).click()

    await expect(page.locator('table')).toBeVisible()
  })

  test('New Estimate button navigates', async ({ page }) => {
    await page.goto('/estimates')

    await page.getByRole('link', { name: 'New Estimate' }).click()
    await page.waitForURL('**/estimates/new')
    expect(page.url()).toContain('/estimates/new')
  })
})
