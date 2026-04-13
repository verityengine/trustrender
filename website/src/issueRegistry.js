/**
 * Blocked Issue Registry
 *
 * Static registry keyed by ValidationResult.rule_id.
 * Defines the human label, blocked path, maximum fix tier,
 * input hints, and whether the issue is diagnostic-only.
 *
 * Used by patchUtils.generatePatches() to classify each blocked
 * error and generate the right fix affordance without ad-hoc
 * conditionals scattered across App.jsx.
 */

export const ISSUE_REGISTRY = {
  'identity.invoice_number': {
    label: 'Missing invoice number',
    blockedPath: 'invoice_number',
    parentPath: null,            // top-level field, no parent indirection
    maxTier: 'A',
    inputHints: ['InvoiceNumber', 'DocNumber', 'invoice_no', 'invoice_number'],
    diagnosticOnly: false,
    inputLabel: 'Enter invoice number',
  },
  'identity.sender_name': {
    label: 'Missing sender name',
    blockedPath: 'sender.name',
    parentPath: 'sender',        // near-match may target the parent object
    maxTier: 'A',
    inputHints: ['CompanyName', 'account_name', 'bill_from_name', 'sender.name'],
    diagnosticOnly: false,
    inputLabel: 'Enter sender name',
  },
  'identity.recipient_name': {
    label: 'Missing recipient name',
    blockedPath: 'recipient.name',
    parentPath: 'recipient',     // near-match may target the parent object
    maxTier: 'A',
    inputHints: ['customer_name', 'bill_to_name', 'recipient.name'],
    diagnosticOnly: false,
    inputLabel: 'Enter recipient name',
  },
  'items.non_empty': {
    label: 'No line items',
    blockedPath: 'items',
    parentPath: null,
    maxTier: 'C',
    inputHints: null,
    diagnosticOnly: true,
    diagnosticMessage: 'Add line items to your JSON payload.',
  },
  'arithmetic.line_total': {
    label: 'Line total contradiction',
    blockedPath: null,
    parentPath: null,
    maxTier: 'C',
    inputHints: null,
    diagnosticOnly: true,
    diagnosticMessage: 'Cannot auto-fix: arithmetic contradiction. Edit the values in your JSON to resolve.',
  },
  'arithmetic.subtotal': {
    label: 'Subtotal contradiction',
    blockedPath: null,
    parentPath: null,
    maxTier: 'C',
    inputHints: null,
    diagnosticOnly: true,
    diagnosticMessage: 'Cannot auto-fix: arithmetic contradiction. Edit the values in your JSON to resolve.',
  },
  'arithmetic.total': {
    label: 'Total contradiction',
    blockedPath: null,
    parentPath: null,
    maxTier: 'C',
    inputHints: null,
    diagnosticOnly: true,
    diagnosticMessage: 'Cannot auto-fix: arithmetic contradiction. Edit the values in your JSON to resolve.',
  },
}

/**
 * Look up a blocked rule_id in the registry.
 * Returns the entry or null for unknown rule_ids.
 */
export function getIssueEntry(ruleId) {
  return ISSUE_REGISTRY[ruleId] || null
}
