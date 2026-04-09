import { test, expect } from '@playwright/test'

test.describe('Dashboard', { tag: '@smoke' }, () => {
  test.setTimeout(30_000)

  test('loads stat cards with live data', async ({ page }) => {
    await page.goto('/dashboard')

    // Wait for loading to clear: "Total Projects" starts as '—' then becomes '124'
    const totalProjectsValue = page.locator('text=124').first()
    await expect(totalProjectsValue).toBeVisible({ timeout: 10_000 })

    // Assert the dollar-prefixed value for Avg ACT Cost / SF
    const dollarValue = page.locator('text=/^\\$[0-9]/')
    await expect(dollarValue.first()).toBeVisible()
  })

  test('cost trend chart renders', async ({ page }) => {
    await page.goto('/dashboard')

    // CostTrendChart renders a recharts SVG
    const svg = page.locator('svg').first()
    await expect(svg).toBeVisible()
  })

  test('view toggle switches between table and board', async ({ page }) => {
    await page.goto('/dashboard')

    // Dashboard defaults to table view — thead should already be visible
    const thead = page.locator('thead')
    await expect(thead).toBeVisible()

    // Switch to board
    await page.getByRole('button', { name: 'Board' }).click()

    // EstimateBoard renders; the thead should disappear from the recent-estimates section
    await expect(thead).not.toBeVisible()

    // Switch back to table
    await page.getByRole('button', { name: 'Table' }).click()
    await expect(thead).toBeVisible()
  })

  test('New Estimate CTA navigates to wizard', async ({ page }) => {
    await page.goto('/dashboard')

    await page.getByRole('link', { name: 'New Estimate' }).click()
    await page.waitForURL('**/estimates/new')
    expect(page.url()).toMatch(/\/estimates\/new$/)
  })
})
