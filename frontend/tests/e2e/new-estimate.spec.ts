/**
 * End-to-end test: upload a real plan PDF and verify the full estimation
 * pipeline produces a saved estimate with scopes and cost data.
 *
 * Prerequisites:
 *   - Next.js dev server running on http://localhost:3000
 *   - FastAPI backend running on http://localhost:8000
 *   - ANTHROPIC_API_KEY set in the backend environment
 *
 * Run:
 *   pnpm exec playwright test tests/e2e/new-estimate.spec.ts
 */

import { test, expect, type Page } from '@playwright/test'
import path from 'path'
import fs from 'fs'

// ---------------------------------------------------------------------------
// Plan PDF — BMG 231 Citi Centre (ACT drawings, one of the 124 training jobs)
// ---------------------------------------------------------------------------
const PLAN_PDF = path.join(
  '/Users/hannibalbaldwin/Library/CloudStorage/Dropbox-SiteZeus/Hannibal Baldwin/+ITBs',
  'BMG 231',
  'BMG 231 Citi Centre - ACT Dwg.pdf',
)
const PROJECT_NAME = 'BMG 231 E2E Test'
const GC_NAME = 'BMG Development'
const API_BASE = 'http://localhost:8000'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Returns the react-dropzone file input (accept="application/pdf,.pdf"). */
function fileInput(page: Page) {
  return page.locator('input[type="file"]')
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

test.describe('New Estimate wizard — full pipeline', () => {
  test.beforeAll(() => {
    if (!fs.existsSync(PLAN_PDF)) {
      test.skip(true, `Plan PDF not found: ${PLAN_PDF} — requires local Dropbox sync`)
    }
  })

  test('uploads PDF, fills details, runs estimation, and creates estimate', async ({ page }) => {
    // ── Step 1: Navigate and upload ─────────────────────────────────────────
    await page.goto('/estimates/new')
    await expect(page.getByText('Upload PDF Plans')).toBeVisible()

    // Attach the PDF to the hidden file input used by react-dropzone
    await fileInput(page).setInputFiles(PLAN_PDF)

    // File should appear in the list
    await expect(page.getByText('BMG 231 Citi Centre - ACT Dwg.pdf')).toBeVisible()

    // Continue button should now be enabled
    const continueBtn = page.getByRole('button', { name: 'Continue →' })
    await expect(continueBtn).toBeEnabled()
    await continueBtn.click()

    // ── Step 2: Project details ──────────────────────────────────────────────
    await expect(page.getByRole('heading', { name: 'Project Details' })).toBeVisible()

    await page.getByPlaceholder('e.g. Seven Pines Jax — AWP/ACT Renovation').fill(PROJECT_NAME)
    await page.getByPlaceholder('e.g. DPR Construction').fill(GC_NAME)

    // Select ACT scope hint to help the model focus
    await page.getByRole('button', { name: 'ACT' }).click()

    const startBtn = page.getByRole('button', { name: 'Start Estimation →' })
    await expect(startBtn).toBeEnabled()
    await startBtn.click()

    // ── Step 3: Processing ───────────────────────────────────────────────────
    await expect(page.getByRole('heading', { name: 'Running Estimation' })).toBeVisible()
    await expect(page.getByText(/AI is reading plans and running cost models/)).toBeVisible()

    // Wait for estimation to complete (up to 2 min — real Claude API call)
    await expect(page.getByText('Estimate complete')).toBeVisible({ timeout: 120_000 })

    // ── View the estimate ────────────────────────────────────────────────────
    const viewLink = page.getByRole('link', { name: 'View Estimate →' })
    await expect(viewLink).toBeVisible()

    // Capture the estimate ID from the href before navigating
    const href = await viewLink.getAttribute('href')
    expect(href).toMatch(/^\/estimates\/[0-9a-f-]{36}$/)
    const estimateId = href!.replace('/estimates/', '')

    await viewLink.click()

    // ── Estimate detail page ─────────────────────────────────────────────────
    await page.waitForURL(`/estimates/${estimateId}`)

    // Project name should appear in the heading / breadcrumb
    await expect(page.getByText(PROJECT_NAME)).toBeVisible()

    // At least one scope row should be present
    // Scope rows have scope-type badges (ACT, AWP, etc.)
    const scopeBadges = page.locator('[class*="scope"], td').filter({ hasText: /^(ACT|AWP|FW|SM|WW)$/ })
    await expect(scopeBadges.first()).toBeVisible({ timeout: 15_000 })

    // Total cost should be non-zero and formatted as currency
    const totalCostEl = page.locator('text=/\\$[0-9,]+/').first()
    await expect(totalCostEl).toBeVisible()

    // ── Verify via API that estimate was persisted ───────────────────────────
    const apiRes = await page.request.get(`${API_BASE}/api/estimates/${estimateId}`)
    expect(apiRes.status()).toBe(200)

    const estimate = await apiRes.json()
    expect(estimate.id).toBe(estimateId)
    expect(estimate.project_name).toBe(PROJECT_NAME)
    expect(Array.isArray(estimate.scopes)).toBe(true)
    expect(estimate.scopes.length).toBeGreaterThan(0)

    const totalCost = estimate.total_cost ?? estimate.scopes.reduce(
      (sum: number, s: { total_cost?: number }) => sum + (s.total_cost ?? 0),
      0,
    )
    expect(totalCost).toBeGreaterThan(0)

    // Sanity-check: ACT scope type present since we sent a hint + ACT PDF
    const scopeTypes: string[] = estimate.scopes.map((s: { scope_type?: string }) => s.scope_type)
    expect(scopeTypes.some((t) => ['ACT', 'AWP', 'FW', 'SM'].includes(t))).toBe(true)
  })
})
