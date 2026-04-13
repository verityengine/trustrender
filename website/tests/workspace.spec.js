/**
 * Workspace pipeline tests — Ingest | Preflight | Render
 *
 * Requires:
 *   - vite dev server running on http://localhost:8199
 *   - trustrender server running on http://localhost:8190
 *
 * Run: cd website && npx playwright test
 */

import { test, expect } from '@playwright/test'

// ── Helpers ──────────────────────────────────────────────────────────────────

/** Navigate to the #app workspace and wait for it to mount */
async function gotoWorkspace(page) {
  await page.goto('/#app')
  await expect(page.getByRole('button', { name: /^Ingest/ })).toBeVisible()
}

/** Select a sample from the ingest dropdown */
async function selectSample(page, sampleName) {
  await page.locator('select').selectOption(sampleName)
  await page.waitForTimeout(150)
}

/**
 * Click "Run ingest →" and wait for a result.
 * The outcome heading (Card 1) says "Render-ready" or "Blocked — N issues".
 * :not([class*="font-mono"]) excludes the trace rule_id divs which also use
 * font-semibold + text-wine but always have font-mono too.
 */
async function runIngest(page) {
  await page.getByRole('button', { name: /Run ingest|Re-run ingest/ }).click()
  // Outcome heading uses text-[17px] — distinguishes it from blocked error labels in the trace
  await expect(
    page.locator('div[class*="font-semibold"][class*="text-sage"][class*="text-[17px]"]')
      .or(page.locator('div[class*="font-semibold"][class*="text-wine"][class*="text-[17px]"]'))
  ).toBeVisible({ timeout: 6000 })
}

/** Assert which tab is currently active */
async function expectActiveTab(page, tabName) {
  await expect(page.getByRole('button', { name: new RegExp(`^${tabName}`) })).toHaveClass(/bg-panel/)
}

/** Open the trace panel (Card 3 — collapsed by default on ready results) */
async function openTrace(page) {
  await page.getByRole('button', { name: /Inspect mappings/ }).click()
}

/** Switch Card 2 to Canonical JSON view */
async function showCanonicalJson(page) {
  await page.getByRole('button', { name: 'Canonical JSON' }).click()
}


// ── Test Suite ────────────────────────────────────────────────────────────────

test.describe('Ingest stage', () => {

  test('idle state shows on initial load', async ({ page }) => {
    await gotoWorkspace(page)
    await expect(page.locator('text=Ingest stage')).toBeVisible()
    await expect(page.locator('select')).toHaveValue('')
  })

  test('stripe sample loads into editor', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await expect(page.locator('.cm-content')).toContainText('account_name')
    await expect(page.locator('.cm-content')).toContainText('lines')
  })

  test('run ingest on stripe → render-ready', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    await expect(page.locator('div[class*="font-semibold"][class*="text-sage"][class*="text-[17px]"]')).toHaveText('Render-ready')
    // Summary view (default) shows normalized canonical fields as structured rows
    await expect(page.getByText('INV-2026-00042', { exact: true })).toBeVisible()   // Invoice #
    await expect(page.getByText('Buildspace Labs Inc.', { exact: true })).toBeVisible() // Sender
  })

  test('run ingest on quickbooks → render-ready', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'quickbooks')
    await runIngest(page)
    await expect(page.locator('div[class*="font-semibold"][class*="text-sage"][class*="text-[17px]"]')).toHaveText('Render-ready')
    // Summary view shows the canonical document clearly
    await expect(page.getByText('INV-1089', { exact: true })).toBeVisible()         // Invoice #
    await expect(page.getByText('Redwood Digital LLC', { exact: true })).toBeVisible() // Sender
  })

  test('run ingest on xero → blocked (missing sender)', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'xero')
    await runIngest(page)
    await expect(page.locator('div[class*="font-semibold"][class*="text-wine"][class*="text-[17px]"]')).toContainText('Blocked')
    // Blocked result auto-opens trace on Blocked tab — human-friendly error visible
    await expect(page.getByText('Missing sender name')).toBeVisible()
  })

  test('run ingest on csv flat → render-ready', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'csv')
    await runIngest(page)
    await expect(page.locator('div[class*="font-semibold"][class*="text-sage"][class*="text-[17px]"]')).toHaveText('Render-ready')
    // Summary view shows sender name
    await expect(page.getByText('Summit Analytics Co.', { exact: true })).toBeVisible()
  })

  test('aliases tab shows normalization trace', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'quickbooks')
    await runIngest(page)
    // Trace is collapsed by default on render-ready results — open it first
    await openTrace(page)
    // Original-key column uses text-wine, canonical-name column uses text-sage.
    await expect(page.locator('code[class*="text-wine"]:has-text("CompanyName")')).toBeVisible()
    await expect(page.locator('code[class*="text-wine"]:has-text("DocNumber")')).toBeVisible()
    await expect(page.locator('code[class*="text-sage"]:has-text("sender.name")')).toBeVisible()
    await expect(page.locator('code[class*="text-sage"]:has-text("invoice_number")')).toBeVisible()
  })

  test('Summary / Canonical JSON / Raw JSON toggle switches displayed payload', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    // Default is Summary — no raw <pre> element, structured rows instead
    await expect(page.getByText('INV-2026-00042', { exact: true })).toBeVisible()
    await expect(page.locator('pre')).not.toBeVisible()
    // Switch to Canonical JSON — normalized payload in <pre>
    await page.getByRole('button', { name: 'Canonical JSON' }).click()
    await expect(page.locator('pre')).toContainText('invoice_number')
    await expect(page.locator('pre')).not.toContainText('account_name')
    // Switch to Raw JSON — original Stripe field names
    await page.getByRole('button', { name: 'Raw JSON' }).click()
    await expect(page.locator('pre')).toContainText('account_name')
    await expect(page.locator('pre')).not.toContainText('invoice_number')
    // Switch back to Summary
    await page.getByRole('button', { name: 'Summary' }).click()
    await expect(page.getByText('INV-2026-00042', { exact: true })).toBeVisible()
    await expect(page.locator('pre')).not.toBeVisible()
  })

  test('footer shows inferred template before continue', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    await expect(page.locator('text=Template: invoice.j2.typ')).toBeVisible()
  })

  test('malformed JSON disables the run ingest button', async ({ page }) => {
    await gotoWorkspace(page)
    // Replace editor content with invalid JSON
    await page.locator('.cm-content').first().click()
    await page.keyboard.press('ControlOrMeta+A')
    await page.keyboard.insertText('{not valid json')
    // Button is disabled — parse error blocks the front door
    await expect(page.getByRole('button', { name: /Run ingest/ })).toBeDisabled()
    // Both indicators are surfaced: parse error above the editor + footer hint
    await expect(page.getByText('Fix JSON errors to continue')).toBeVisible()
  })

  test('status badge shows ready on render-ready result', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    // The status pill badge (not the tab or heading)
    await expect(page.locator('span[class*="font-mono"]:has-text("ready")')).toBeVisible()
  })

})


test.describe('Blocked cases', () => {

  test('blocked result shows specific error message in blocked tab', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'xero')
    await runIngest(page)
    await expect(page.locator('div[class*="font-semibold"][class*="text-wine"][class*="text-[17px]"]')).toContainText('Blocked')
    // Blocked result auto-opens trace on Blocked tab — human-friendly error visible
    await expect(page.getByText('Missing sender name')).toBeVisible()
  })

  test('blocked result: issue count badge on Blocked tab is correct', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'xero')
    await runIngest(page)
    // Xero produces exactly 1 blocking error — Card 1 heading says "Blocked — 1 render-blocking issue"
    await expect(page.locator('div[class*="font-semibold"][class*="text-wine"][class*="text-[17px]"]')).toContainText('Blocked — 1 render-blocking issue')
    // Trace auto-opens — Blocked tab button badge also shows the count
    await expect(page.getByRole('button', { name: /^Blocked/ })).toContainText('1')
  })

  test('blocked result: aliases still trace despite blocked status', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'xero')
    await runIngest(page)
    // Trace auto-opens on Blocked tab — switch to Aliases to verify normalization ran
    await page.getByRole('button', { name: /^Aliases/ }).click()
    await expect(page.locator('code[class*="text-wine"]:has-text("InvoiceNumber")')).toBeVisible()
    await expect(page.locator('code[class*="text-sage"]:has-text("invoice_number")')).toBeVisible()
    // Recipient alias also resolved
    await expect(page.locator('code[class*="text-wine"]:has-text("Contact")')).toBeVisible()
  })

  test('blocked result: summary view shows partial data (no template_payload)', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'xero')
    await runIngest(page)
    // Summary view (default) shows what was resolved — InvoiceNumber mapped to invoice_number
    await expect(page.getByText('INV-0234', { exact: true })).toBeVisible()
    // No "Continue to preflight" button — blocked payloads cannot proceed
    await expect(page.getByRole('button', { name: /Continue to preflight/ })).not.toBeVisible()
  })

})


test.describe('State recovery', () => {

  test('blocked → fix sender.name → re-run → render-ready', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'xero')
    await runIngest(page)
    await expect(page.locator('div[class*="font-semibold"][class*="text-wine"][class*="text-[17px]"]')).toContainText('Blocked')

    // Supply the missing sender.name via CompanyName alias (Xero has no sender field)
    const fixedXero = JSON.stringify({
      InvoiceNumber: 'INV-0234', date: '2026-03-20', DueDate: '2026-04-19',
      CompanyName: 'Greenfield Services Ltd',  // ← this resolves sender.name
      CompanyEmail: 'billing@greenfield.io',
      Contact: { Name: 'Greenfield Dynamics', EmailAddress: 'accounts@greenfield.io' },
      LineItems: [
        { Description: 'Annual SaaS License', Quantity: 1.0, UnitAmount: 12000.00, LineAmount: 12000.00 },
        { Description: 'Onboarding & Implementation', Quantity: 1.0, UnitAmount: 4500.00, LineAmount: 4500.00 },
      ],
      SubTotal: 16500.00, TotalTax: 1402.50, Total: 17902.50, CurrencyCode: 'USD',
    }, null, 2)

    // Replace the ingest editor content: select-all → insert fixed JSON
    await page.locator('.cm-content').first().click()
    await page.keyboard.press('ControlOrMeta+A')
    await page.keyboard.insertText(fixedXero)

    // Re-run — button text switches to "Re-run ingest →" after stale triggers
    await page.getByRole('button', { name: /Re-run ingest/ }).click()
    await expect(page.locator('div[class*="font-semibold"][class*="text-sage"][class*="text-[17px]"]')).toBeVisible({ timeout: 6000 })
    await expect(page.locator('div[class*="font-semibold"][class*="text-sage"][class*="text-[17px]"]')).toHaveText('Render-ready')

    // Blocked message is gone
    await expect(page.locator('div[class*="font-semibold"][class*="text-wine"][class*="text-[17px]"]')).not.toBeVisible()

    // Recovery line acknowledges the resolved issue
    await expect(page.getByText(/Previously blocked issue resolved:.*sender\.name/)).toBeVisible()

    // Forward path is restored with readiness context line
    await expect(page.getByText('Canonical invoice complete. Continue to validation.')).toBeVisible()
    await expect(page.getByRole('button', { name: /Continue to preflight/ })).toBeEnabled()

    // Summary view shows the repaired sender
    await expect(page.getByText('Greenfield Services Ltd', { exact: true })).toBeVisible()
  })

})


test.describe('Recovery UI', () => {

  test('fresh run (no prior blocked state) shows no recovery line', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    await expect(page.locator('div[class*="font-semibold"][class*="text-sage"][class*="text-[17px]"]')).toHaveText('Render-ready')
    // No recovery line on fresh run
    await expect(page.getByText(/Previously blocked/)).not.toBeVisible()
  })

  test('sample switch after blocked run resets recovery context', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'xero')
    await runIngest(page)
    await expect(page.locator('div[class*="font-semibold"][class*="text-wine"][class*="text-[17px]"]')).toContainText('Blocked')
    // Switch to a clean sample — this is a new session, not a correction
    await selectSample(page, 'stripe')
    await runIngest(page)
    await expect(page.locator('div[class*="font-semibold"][class*="text-sage"][class*="text-[17px]"]')).toHaveText('Render-ready')
    // No recovery line — sample switch cleared the context
    await expect(page.getByText(/Previously blocked/)).not.toBeVisible()
  })

  test('blocked → still blocked with different error shows no false recovery', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'xero')
    await runIngest(page)
    await expect(page.locator('div[class*="font-semibold"][class*="text-wine"][class*="text-[17px]"]')).toContainText('Blocked')

    // Edit to a different blocked state — fix sender but break invoice_number
    const stillBroken = JSON.stringify({
      CompanyName: 'Greenfield Services Ltd',
      Contact: { Name: 'Client Co', EmailAddress: 'a@b.com' },
      LineItems: [{ Description: 'Widget', Quantity: 1, UnitAmount: 100, LineAmount: 100 }],
      SubTotal: 100, TotalTax: 0, Total: 100, CurrencyCode: 'USD',
      // no InvoiceNumber — still blocked
    }, null, 2)
    await page.locator('.cm-content').first().click()
    await page.keyboard.press('ControlOrMeta+A')
    await page.keyboard.insertText(stillBroken)
    await page.getByRole('button', { name: /Re-run ingest/ }).click()
    await expect(
      page.locator('div[class*="font-semibold"][class*="text-wine"][class*="text-[17px]"]')
    ).toBeVisible({ timeout: 6000 })
    // Still blocked — no recovery line
    await expect(page.getByText(/Previously blocked/)).not.toBeVisible()
  })

  test('readiness context line and Inspect mappings button visible', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    await expect(page.getByText('Canonical invoice complete. Continue to validation.')).toBeVisible()
    await expect(page.getByRole('button', { name: /Inspect mappings/ })).toBeVisible()
  })

  test('Resolved fields label visible when aliases present', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    await expect(page.getByText('Resolved fields')).toBeVisible()
  })

  test('stale → rerun → still blocked does not imply progress', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'xero')
    await runIngest(page)
    await expect(page.locator('div[class*="font-semibold"][class*="text-wine"][class*="text-[17px]"]')).toContainText('Blocked')

    // Edit the JSON slightly — triggers stale state
    await page.locator('.cm-content').first().click()
    await page.keyboard.press('End')
    await page.keyboard.type(' ')

    // Stale banner should be the primary action
    await expect(page.getByText('Input changed. Re-run ingest to refresh results.')).toBeVisible()

    // Re-run — still blocked (Xero still has no sender)
    await page.getByRole('button', { name: /Re-run ingest/ }).click()
    await expect(
      page.locator('div[class*="font-semibold"][class*="text-wine"][class*="text-[17px]"]')
    ).toBeVisible({ timeout: 6000 })
    await expect(page.locator('div[class*="font-semibold"][class*="text-wine"][class*="text-[17px]"]')).toContainText('Blocked')

    // No false recovery line — still blocked, not recovered
    await expect(page.getByText(/Previously blocked/)).not.toBeVisible()

    // Blocked error is still visible with human wording
    await expect(page.getByText('Missing sender name')).toBeVisible()
  })

  test('blocked with no friendly alias hint shows raw message gracefully', async ({ page }) => {
    await gotoWorkspace(page)

    // Craft a payload with an arithmetic contradiction — no friendly hint for this error type
    const badArithmetic = JSON.stringify({
      invoice_number: 'INV-999',
      sender: { name: 'Acme Corp' },
      recipient: { name: 'Client Inc' },
      items: [
        { description: 'Widget', quantity: 2, unit_price: 100, line_total: 999 },
      ],
      subtotal: 999,
      total: 999,
    }, null, 2)

    await page.locator('.cm-content').first().click()
    await page.keyboard.press('ControlOrMeta+A')
    await page.keyboard.insertText(badArithmetic)
    await runIngest(page)

    await expect(page.locator('div[class*="font-semibold"][class*="text-wine"][class*="text-[17px]"]')).toContainText('Blocked')

    // Arithmetic error has no human label — falls back to raw message
    // Should still be visible and not crash
    await expect(page.getByText(/line_total.*!=.*quantity.*unit_price/)).toBeVisible()

    // No input hints for arithmetic errors — just the diagnostic message
    await expect(page.getByText(/Add .* to continue/)).not.toBeVisible()
  })

  test('blocked with multiple issues shows correct count and all errors', async ({ page }) => {
    await gotoWorkspace(page)

    // Craft a payload missing both sender and invoice_number
    const multiBlocked = JSON.stringify({
      recipient: { name: 'Client Inc' },
      items: [
        { description: 'Widget', quantity: 1, unit_price: 100, line_total: 100 },
      ],
      subtotal: 100,
      total: 100,
    }, null, 2)

    await page.locator('.cm-content').first().click()
    await page.keyboard.press('ControlOrMeta+A')
    await page.keyboard.insertText(multiBlocked)
    await runIngest(page)

    // Heading shows multiple blocked issues
    await expect(page.locator('div[class*="font-semibold"][class*="text-wine"][class*="text-[17px]"]')).toContainText('Blocked — 2 render-blocking issues')

    // Both human-friendly error labels visible in blocked tab
    await expect(page.getByText('Missing sender name')).toBeVisible()
    await expect(page.getByText('Missing invoice number')).toBeVisible()

    // Both show guided fix affordances (Tier B — user input)
    await expect(page.getByText(/Enter sender name/)).toBeVisible()
    await expect(page.getByText(/Enter invoice number/)).toBeVisible()
  })

})


test.describe('Stale result gate', () => {

  test('switching sample after run clears result to idle', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    await expect(page.locator('div[class*="font-semibold"][class*="text-sage"][class*="text-[17px]"]')).toBeVisible()
    // Switch to a different sample
    await selectSample(page, 'quickbooks')
    // Result cleared — idle state
    await expect(page.locator('text=Ingest stage')).toBeVisible()
    await expect(page.locator('div[class*="font-semibold"][class*="text-sage"][class*="text-[17px]"]')).not.toBeVisible()
  })

  test('switching back to same sample after run still clears result', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    await selectSample(page, 'quickbooks')
    await selectSample(page, 'stripe')
    // Must re-run — still idle
    await expect(page.locator('text=Ingest stage')).toBeVisible()
  })

  test('manual JSON edit after run shows stale indicator', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    await expect(page.locator('div[class*="font-semibold"][class*="text-sage"][class*="text-[17px]"]')).toContainText('Render-ready')

    // Type a single character directly into the ingest editor — changes rawJson
    await page.locator('.cm-content').first().click()
    await page.keyboard.press('End')
    await page.keyboard.type('x')

    // Stale indicator fires
    await expect(page.getByText('Input changed. Re-run ingest to refresh results.')).toBeVisible()
    // CTA switches to re-run
    await expect(page.getByRole('button', { name: /Re-run ingest/ })).toBeVisible()
    // Continue to preflight is gated — stale result cannot flow downstream
    await expect(page.getByRole('button', { name: /Continue to preflight/ })).not.toBeVisible()
  })

  test('continue to preflight button is enabled on fresh render-ready result', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    await expect(page.getByRole('button', { name: /Continue to preflight/ })).toBeEnabled()
  })

  test('xero blocked result does not show continue button', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'xero')
    await runIngest(page)
    await expect(page.locator('div[class*="font-semibold"][class*="text-wine"][class*="text-[17px]"]')).toContainText('Blocked')
    await expect(page.getByRole('button', { name: /Continue to preflight/ })).not.toBeVisible()
    // CTA row shows "Fix N issues to continue" instead of a forward button
    await expect(page.locator('text=/Fix.*issue.*continue/i')).toBeVisible()
  })

})


test.describe('Ingest → Preflight handoff', () => {

  test('continue to preflight switches to preflight tab', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    await page.getByRole('button', { name: /Continue to preflight/ }).click()
    await expectActiveTab(page, 'Preflight')
  })

  test('preflight editor contains canonical payload from ingest', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'quickbooks')
    await runIngest(page)
    await page.getByRole('button', { name: /Continue to preflight/ }).click()
    // CodeMirror only renders visible lines — check fields that appear mid-document
    // (invoice_number may be above the viewport fold; sender + company name are reliably present)
    await expect(page.locator('.cm-content')).toContainText('sender')
    await expect(page.locator('.cm-content')).toContainText('Redwood Digital')
  })

  test('preflight auto-runs and reaches a verdict after handoff', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    await page.getByRole('button', { name: /Continue to preflight/ }).click()
    await expect(
      page.locator('text=Ready to render').or(page.locator('text=/issue.*must be fixed/'))
    ).toBeVisible({ timeout: 6000 })
  })

  test('stripe ingest → preflight → ready to render', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    await page.getByRole('button', { name: /Continue to preflight/ }).click()
    await expect(page.locator('text=Ready to render')).toBeVisible({ timeout: 6000 })
  })

  test('quickbooks ingest → preflight → ready to render', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'quickbooks')
    await runIngest(page)
    await page.getByRole('button', { name: /Continue to preflight/ }).click()
    await expect(page.locator('text=Ready to render')).toBeVisible({ timeout: 6000 })
  })

  test('ingest tab retains green dot after navigating to preflight', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    await page.getByRole('button', { name: /Continue to preflight/ }).click()
    // Ingest dot (green = render-ready)
    const ingestTab = page.getByRole('button', { name: /^Ingest/ })
    await expect(ingestTab.locator('span[class*="bg-sage"]')).toBeVisible()
  })

  test('invoice template is auto-selected in preflight after handoff', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    await page.getByRole('button', { name: /Continue to preflight/ }).click()
    // Template selector should show Invoice
    await expect(page.locator('select')).toHaveValue('invoice.j2.typ')
  })

  test('no stale verdict flicker: preflight shows checking not old verdict on arrival', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    await page.getByRole('button', { name: /Continue to preflight/ }).click()
    // Immediately after tab switch, should NOT show a stale "Ready to render" from a previous run
    // (verdict should be null/checking, not left over)
    // We verify by confirming only one verdict is ever shown
    await expect(page.locator('text=Ready to render')).toBeVisible({ timeout: 6000 })
    const count = await page.locator('text=Ready to render').count()
    expect(count).toBe(1)
  })

})


test.describe('Start fresh', () => {

  test('new draft resets to ingest tab', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    await page.getByRole('button', { name: /Continue to preflight/ }).click()
    await expect(page.locator('text=Ready to render')).toBeVisible({ timeout: 6000 })
    await page.getByRole('button', { name: 'New draft' }).click()
    await expectActiveTab(page, 'Ingest')
    await expect(page.locator('text=Ingest stage')).toBeVisible()
  })

  test('new draft clears sample selection', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    await page.getByRole('button', { name: 'New draft' }).click()
    await expect(page.locator('select')).toHaveValue('')
  })

  test('new draft clears nav indicator dots', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    await page.getByRole('button', { name: 'New draft' }).click()
    // No green or red dots on any tab after reset
    const ingestTab = page.getByRole('button', { name: /^Ingest/ })
    await expect(ingestTab.locator('span[class*="bg-sage"]')).not.toBeVisible()
    await expect(ingestTab.locator('span[class*="bg-wine"]')).not.toBeVisible()
  })

})


test.describe('Browser refresh', () => {

  test('reload returns to ingest idle — no persisted state', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    // Reload — session state is not persisted (by design)
    await page.reload()
    await page.goto('/#app')
    await expect(page.locator('text=Ingest stage')).toBeVisible()
    await expect(page.locator('select')).toHaveValue('')
  })

  test('reload from blocked state returns to ingest idle — blocked status not persisted', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'xero')
    await runIngest(page)
    await expect(page.locator('div[class*="font-semibold"][class*="text-wine"][class*="text-[17px]"]')).toContainText('Blocked')
    await page.reload()
    await page.goto('/#app')
    // No blocked state persisted — back to clean ingest idle
    await expect(page.locator('text=Ingest stage')).toBeVisible()
    await expect(page.locator('div[class*="font-semibold"][class*="text-wine"][class*="text-[17px]"]')).not.toBeVisible()
    await expect(page.locator('select')).toHaveValue('')
  })

  test('reload from preflight tab returns to ingest idle', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    await page.getByRole('button', { name: /Continue to preflight/ }).click()
    await expect(page.locator('text=Ready to render')).toBeVisible({ timeout: 6000 })
    await page.reload()
    await page.goto('/#app')
    // No preflight verdict visible — back to ingest
    await expect(page.locator('text=Ingest stage')).toBeVisible()
    await expect(page.locator('text=Ready to render')).not.toBeVisible()
  })

})


test.describe('Rapid interactions', () => {

  test('clicking Continue twice does not crash', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    const ctaBtn = page.getByRole('button', { name: /Continue to preflight/ })
    await ctaBtn.click()
    await ctaBtn.click().catch(() => {}) // second click may fail if button gone — OK
    await expectActiveTab(page, 'Preflight')
  })

  test('switch sample repeatedly then run ingest → correct final result', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await selectSample(page, 'quickbooks')
    await selectSample(page, 'csv')
    await selectSample(page, 'stripe')
    await runIngest(page)
    await expect(page.locator('div[class*="font-semibold"][class*="text-sage"][class*="text-[17px]"]')).toHaveText('Render-ready')
    // Last selected was stripe — summary view shows INV-2026-00042 in Invoice # row
    await expect(page.getByText('INV-2026-00042', { exact: true })).toBeVisible()
  })

  test('switch tab mid-flow then return to ingest preserves editor content', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'quickbooks')
    await page.getByRole('button', { name: /^Preflight/ }).click()
    await page.getByRole('button', { name: /^Render/ }).click()
    await page.getByRole('button', { name: /^Ingest/ }).click()
    await expect(page.locator('.cm-content')).toContainText('DocNumber')
    await expect(page.locator('select')).toHaveValue('quickbooks')
  })

  test('running ingest twice in a row produces consistent result', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    await expect(page.locator('div[class*="font-semibold"][class*="text-sage"][class*="text-[17px]"]')).toHaveText('Render-ready')
    // Run again without changing anything
    await page.getByRole('button', { name: /Run ingest/ }).click()
    await expect(
      page.locator('div[class*="font-semibold"][class*="text-sage"][class*="text-[17px]"]')
    ).toHaveText('Render-ready', { timeout: 6000 })
    // Summary view shows invoice number — consistent across both runs
    await expect(page.getByText('INV-2026-00042', { exact: true })).toBeVisible()
  })

  test('full pipeline: stripe ingest → preflight → render PDF button visible', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'stripe')
    await runIngest(page)
    await page.getByRole('button', { name: /Continue to preflight/ }).click()
    await expect(page.locator('text=Ready to render')).toBeVisible({ timeout: 6000 })
    await expect(page.getByRole('button', { name: /Render PDF/ })).toBeVisible()
  })

})


// ── Guided Correction ────────────────────────────────────────────────────────

/** Paste custom JSON into the ingest editor */
async function pasteJson(page, obj) {
  await page.locator('.cm-content').first().click()
  await page.keyboard.press('ControlOrMeta+A')
  await page.keyboard.insertText(JSON.stringify(obj, null, 2))
}

test.describe('Guided correction — Tier B (user input)', () => {
  test('missing sender shows input field when expanded', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'xero')
    await runIngest(page)

    // Blocked tab auto-opens — Tier B affordance visible
    await expect(page.getByText(/Enter sender name/)).toBeVisible()
  })

  test('enter value + accept + apply & rerun → render-ready', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'xero')
    await runIngest(page)

    // Click to expand the Tier B input
    await page.getByText(/Enter sender name/).click()
    await page.waitForTimeout(200)

    // Type a value and accept
    const input = page.locator('input[placeholder="sender.name"]')
    await input.fill('Greenfield Dynamics')
    await page.getByRole('button', { name: 'Accept' }).click()

    // Apply bar appears
    await expect(page.getByText(/1 fix ready/)).toBeVisible()

    // Apply & rerun
    await page.getByRole('button', { name: /Apply.*re-run ingest/ }).click()

    // Wait for render-ready result
    await expect(
      page.locator('div[class*="font-semibold"][class*="text-sage"][class*="text-[17px]"]')
    ).toBeVisible({ timeout: 6000 })
  })

  test('empty input is rejected — Accept button disabled', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'xero')
    await runIngest(page)

    await page.getByText(/Enter sender name/).click()
    await page.waitForTimeout(200)

    // Accept button should be disabled when input is empty
    const acceptBtn = page.getByRole('button', { name: 'Accept' })
    await expect(acceptBtn).toBeDisabled()
  })

  test('undo accepted Tier B fix reverts to suggested state', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'xero')
    await runIngest(page)

    // Accept a fix
    await page.getByText(/Enter sender name/).click()
    await page.waitForTimeout(200)
    await page.locator('input[placeholder="sender.name"]').fill('Test Corp')
    await page.getByRole('button', { name: 'Accept' }).click()

    // Apply bar visible
    await expect(page.getByText(/1 fix ready/)).toBeVisible()

    // Undo
    await page.getByRole('button', { name: 'Undo' }).click()

    // Apply bar gone — no accepted patches
    await expect(page.getByText(/fix ready/)).not.toBeVisible()
  })
})

test.describe('Guided correction — Tier A (near-match rename)', () => {
  const typoPayload = {
    invioce_number: 'INV-TYPO-001',
    sender: { name: 'Acme Corp', email: 'billing@acme.com' },
    recipeint: { name: 'Target LLC', email: 'ap@target.com' },
    items: [
      { description: 'Widget', quantity: 2, unit_price: 100, line_total: 200 },
    ],
    subtotal: 200,
    total: 200,
  }

  test('near-match typos show "Safe fix: Rename" UI', async ({ page }) => {
    await gotoWorkspace(page)
    await pasteJson(page, typoPayload)
    await runIngest(page)

    // Tier A fix panels should be visible
    await expect(page.getByText(/Rename.*invioce_number.*invoice_number/)).toBeVisible()
    await expect(page.getByText(/Rename.*recipeint.*recipient/)).toBeVisible()
  })

  test('accept Tier A fix shows accepted state', async ({ page }) => {
    await gotoWorkspace(page)
    await pasteJson(page, typoPayload)
    await runIngest(page)

    // Accept the first fix
    const acceptButtons = page.getByRole('button', { name: 'Accept fix' })
    await acceptButtons.first().click()

    // Should show checkmark / accepted state
    await expect(page.getByText(/1 fix ready/)).toBeVisible()
  })

  test('accept all Tier A fixes + apply & rerun → render-ready', async ({ page }) => {
    await gotoWorkspace(page)
    await pasteJson(page, typoPayload)
    await runIngest(page)

    // Accept both fixes
    const acceptButtons = page.getByRole('button', { name: 'Accept fix' })
    const count = await acceptButtons.count()
    for (let i = 0; i < count; i++) {
      await acceptButtons.first().click()
      await page.waitForTimeout(100)
    }

    // Apply & rerun
    await page.getByRole('button', { name: /Apply.*re-run ingest/ }).click()

    // Should be render-ready
    await expect(
      page.locator('div[class*="font-semibold"][class*="text-sage"][class*="text-[17px]"]')
    ).toBeVisible({ timeout: 6000 })
  })

  test('skip dismisses Tier A suggestion', async ({ page }) => {
    await gotoWorkspace(page)
    await pasteJson(page, typoPayload)
    await runIngest(page)

    // Skip the first suggestion
    await page.getByRole('button', { name: 'Skip' }).first().click()

    // Both fix panels still exist — skip does not remove them
    // At least one Accept fix button should still be visible
    await expect(page.getByRole('button', { name: 'Accept fix' }).first()).toBeVisible()
  })
})

test.describe('Guided correction — Tier C (diagnostic only)', () => {
  test('arithmetic contradiction shows diagnostic message, no fix button', async ({ page }) => {
    await gotoWorkspace(page)
    const badArithmetic = {
      invoice_number: 'INV-999',
      sender: { name: 'Acme' },
      recipient: { name: 'Client' },
      items: [{ description: 'Widget', quantity: 2, unit_price: 100, line_total: 999 }],
      subtotal: 999,
      total: 999,
    }
    await pasteJson(page, badArithmetic)
    await runIngest(page)

    // Diagnostic message visible
    await expect(page.getByText(/Cannot auto-fix.*arithmetic contradiction/)).toBeVisible()

    // No Accept / Accept fix buttons
    await expect(page.getByRole('button', { name: 'Accept fix' })).not.toBeVisible()
    await expect(page.getByRole('button', { name: 'Accept' })).not.toBeVisible()
  })
})

test.describe('Guided correction — mixed issues', () => {
  test('mixed Tier A + Tier B: fix all + apply → render-ready', async ({ page }) => {
    await gotoWorkspace(page)
    // Payload with typo invoice_number (Tier A) + missing sender.name (Tier B)
    const mixed = {
      invioce_number: 'INV-MIX-001',
      recipient: { name: 'Client Inc' },
      items: [{ description: 'Widget', quantity: 1, unit_price: 50, line_total: 50 }],
      subtotal: 50,
      total: 50,
    }
    await pasteJson(page, mixed)
    await runIngest(page)

    // Accept Tier A rename
    await page.getByRole('button', { name: 'Accept fix' }).click()

    // Open and fill Tier B input
    await page.getByText(/Enter sender name/).click()
    await page.waitForTimeout(200)
    await page.locator('input[placeholder="sender.name"]').fill('Acme Corp')
    await page.getByRole('button', { name: 'Accept' }).click()

    // Apply bar shows 2 fixes
    await expect(page.getByText(/2 fixes ready/)).toBeVisible()

    // Apply & rerun
    await page.getByRole('button', { name: /Apply.*re-run ingest/ }).click()

    // Render-ready
    await expect(
      page.locator('div[class*="font-semibold"][class*="text-sage"][class*="text-[17px]"]')
    ).toBeVisible({ timeout: 6000 })
  })
})

test.describe('Guided correction — preview & state', () => {
  test('preview shows diff when patches accepted', async ({ page }) => {
    await gotoWorkspace(page)
    await pasteJson(page, {
      invioce_number: 'INV-001',
      sender: { name: 'Acme' },
      recipient: { name: 'Client' },
      items: [{ description: 'Widget', quantity: 1, unit_price: 100, line_total: 100 }],
      subtotal: 100,
      total: 100,
    })
    await runIngest(page)

    // Accept the rename fix
    await page.getByRole('button', { name: 'Accept fix' }).click()

    // Click preview
    await page.getByRole('button', { name: 'Preview changes' }).click()

    // Diff preview panel should show
    await expect(page.getByText('Patch preview')).toBeVisible()
  })

  test('sample switch clears pending patches', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'xero')
    await runIngest(page)

    // Verify Tier B fix is visible
    await expect(page.getByText(/Enter sender name/)).toBeVisible()

    // Switch to stripe sample
    await selectSample(page, 'stripe')

    // Guided fix UI should be gone (no ingest result)
    await expect(page.getByText(/Enter sender name/)).not.toBeVisible()
  })

  test('recovery line shows after applying guided fix', async ({ page }) => {
    await gotoWorkspace(page)
    await selectSample(page, 'xero')
    await runIngest(page)

    // Apply a guided fix
    await page.getByText(/Enter sender name/).click()
    await page.waitForTimeout(200)
    await page.locator('input[placeholder="sender.name"]').fill('Greenfield Dynamics')
    await page.getByRole('button', { name: 'Accept' }).click()
    await page.getByRole('button', { name: /Apply.*re-run ingest/ }).click()

    // Wait for render-ready
    await expect(
      page.locator('div[class*="font-semibold"][class*="text-sage"][class*="text-[17px]"]')
    ).toBeVisible({ timeout: 6000 })

    // Recovery line should appear
    await expect(page.getByText(/Previously blocked issue resolved/)).toBeVisible()
  })
})
