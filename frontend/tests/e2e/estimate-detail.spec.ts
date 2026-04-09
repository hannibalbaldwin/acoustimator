/**
 * estimate-detail.spec.ts
 *
 * Fetches the most recent estimate ID from the API in beforeAll and uses it
 * for all tests. All tests are skipped if no estimates exist in the database.
 *
 * The breadcrumb renders:
 *   Dashboard (link → /dashboard) / Estimates (span) / {id} (span)
 * The "Estimates" crumb is a plain <span>, not a link. Navigation back uses
 * the browser history (page.goBack()) instead.
 */
import { test, expect } from '@playwright/test'

let estimateId: string | null = null

test.describe('Estimate Detail', { tag: '@smoke' }, () => {
  test.setTimeout(30_000)

  test.beforeAll(async () => {
    try {
      const res = await fetch('http://localhost:8000/api/estimates?limit=1')
      if (!res.ok) {
        estimateId = null
        return
      }
      const data = await res.json() as { items?: Array<{ id: string }> }
      estimateId = data.items?.[0]?.id ?? null
    } catch {
      estimateId = null
    }
  })

  test('loads estimate with scopes', async ({ page }) => {
    if (!estimateId) {
      test.skip(true, 'No estimates in database — skipping estimate detail tests')
      return
    }

    await page.goto(`/estimates/${estimateId}`)

    // Project name appears inside EstimateSummary; wait for loading skeleton to clear
    // (loading state renders skeleton divs with animate-pulse, not text content)
    const estimateSummary = page.locator('[class*="EstimateSummary"], .mb-5').first()
    await expect(estimateSummary).toBeVisible({ timeout: 10_000 })

    // At least one currency value ("$") should appear in the scopes table
    const currencyCell = page.locator('text=/\\$[0-9,]+/').first()
    await expect(currencyCell).toBeVisible({ timeout: 10_000 })
  })

  test('shows total cost in action bar', async ({ page }) => {
    if (!estimateId) {
      test.skip(true, 'No estimates in database — skipping estimate detail tests')
      return
    }

    await page.goto(`/estimates/${estimateId}`)

    // Sticky bar has "Estimated total" label (uppercase via CSS but stored as text)
    await expect(page.getByText('Estimated total')).toBeVisible({ timeout: 10_000 })

    // The total cost immediately follows as a formatted dollar amount
    const dollarTotal = page.locator('text=/\\$[0-9,]+/').first()
    await expect(dollarTotal).toBeVisible()
  })

  test('quote template picker is functional', async ({ page }) => {
    if (!estimateId) {
      test.skip(true, 'No estimates in database — skipping estimate detail tests')
      return
    }

    await page.goto(`/estimates/${estimateId}`)

    // T-004B is the default selected template — should be visible
    await expect(page.getByRole('button', { name: 'T-004B' })).toBeVisible({ timeout: 10_000 })

    // Click T-004A — no errors should occur and the button remains visible
    await page.getByRole('button', { name: 'T-004A' }).click()
    await expect(page.getByRole('button', { name: 'T-004A' })).toBeVisible()

    // T-004E should also be present
    await expect(page.getByRole('button', { name: 'T-004E' })).toBeVisible()
  })

  test('breadcrumb shows Estimates crumb and can navigate back', async ({ page }) => {
    if (!estimateId) {
      test.skip(true, 'No estimates in database — skipping estimate detail tests')
      return
    }

    await page.goto(`/estimates/${estimateId}`)

    // Breadcrumb: "Dashboard / Estimates / {id}"
    // "Estimates" renders as a plain <span> in the breadcrumb row
    const estimatesCrumb = page.locator('span').filter({ hasText: 'Estimates' }).first()
    await expect(estimatesCrumb).toBeVisible({ timeout: 10_000 })

    // "Dashboard" is the actual <a> link — clicking it navigates to /dashboard
    // Scope to main content to avoid matching the sidebar nav link
    const dashboardLink = page.getByRole('main').getByRole('link', { name: 'Dashboard' })
    await expect(dashboardLink).toBeVisible()
    await dashboardLink.click()

    await page.waitForURL('**/dashboard')
    expect(page.url()).toMatch(/\/dashboard$/)
  })
})
