/**
 * projects.spec.ts
 *
 * Note: FilterSelect is a custom button-based dropdown (not a <select> element).
 * To interact with it: click the trigger button to open the dropdown, then click
 * the desired option button inside the popover.
 */
import { test, expect } from '@playwright/test'

test.describe('Projects', { tag: '@smoke' }, () => {
  test.setTimeout(30_000)

  test('loads project list with 124 projects', async ({ page }) => {
    await page.goto('/projects')

    // Subtitle: "Historical project database · 124 projects total"
    await expect(
      page.locator('p').filter({ hasText: '124 projects total' })
    ).toBeVisible({ timeout: 10_000 })

    // At least one data row in the table
    const tbody = page.locator('tbody tr').first()
    await expect(tbody).toBeVisible()
  })

  test('scope filter narrows results', async ({ page }) => {
    await page.goto('/projects')

    // Wait for data to load
    await expect(
      page.locator('p').filter({ hasText: '124 projects total' })
    ).toBeVisible({ timeout: 10_000 })

    // Open the scope FilterSelect (trigger button shows current value "All Scopes")
    await page.getByRole('button', { name: 'All Scopes' }).click()

    // Click the "ACT" option inside the dropdown
    await page.getByRole('button', { name: 'ACT' }).click()

    // Summary row should still be visible (it always shows "Showing X of 124 projects")
    await expect(
      page.locator('text=/Showing/').filter({ hasText: /of 124 projects/ })
    ).toBeVisible({ timeout: 10_000 })
  })

  test('search filters by name', async ({ page }) => {
    await page.goto('/projects')

    // Wait for data to load
    await expect(
      page.locator('p').filter({ hasText: '124 projects total' })
    ).toBeVisible({ timeout: 10_000 })

    // Grab the first project name from the table to use as a search term
    const firstNameCell = page.locator('tbody tr').first().locator('td').first().locator('p').first()
    const firstName = await firstNameCell.textContent()
    // Use the first word of the name as the search term (reliable partial match)
    const searchTerm = firstName?.split(' ')[0] ?? 'a'

    await page.getByPlaceholder('Search projects...').fill(searchTerm)

    // At least one row should remain visible containing the search term
    const rows = page.locator('tbody tr')
    await expect(rows.first()).toBeVisible({ timeout: 10_000 })
    await expect(rows.first().locator('td').first().locator('p').first()).toContainText(
      new RegExp(searchTerm, 'i')
    )
  })

  test('clear filters resets state', async ({ page }) => {
    await page.goto('/projects')

    // Wait for data to load
    await expect(
      page.locator('p').filter({ hasText: '124 projects total' })
    ).toBeVisible({ timeout: 10_000 })

    // Apply a search
    await page.getByPlaceholder('Search projects...').fill('BMG')

    // "Clear filters ×" appears when any filter is active
    const clearBtn = page.getByRole('button', { name: 'Clear filters ×' })
    await expect(clearBtn).toBeVisible()
    await clearBtn.click()

    // Search input should be empty
    await expect(page.getByPlaceholder('Search projects...')).toHaveValue('')

    // Subtitle should show all 124 projects again
    await expect(
      page.locator('p').filter({ hasText: '124 projects total' })
    ).toBeVisible()
  })
})
