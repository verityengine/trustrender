/**
 * Unit tests for patchUtils.js and issueRegistry.js
 *
 * Run: cd website && npx vitest run tests/patchUtils.test.js
 */

import { describe, it, expect } from 'vitest'
import {
  resolveValueAtPath,
  setValueAtPath,
  renameKeyAtPath,
  generatePatches,
  applyPatches,
  computePatchDiff,
} from '../src/patchUtils.js'
import { ISSUE_REGISTRY, getIssueEntry } from '../src/issueRegistry.js'

// ── Helpers ──────────────────────────────────────────────────────────

/** Build a minimal ingest result for testing */
function blockedResult({ errors = [], unknownFields = [] }) {
  return {
    status: 'blocked',
    render_ready: false,
    canonical: {},
    template_payload: null,
    errors,
    warnings: [],
    normalizations: [],
    computed_fields: [],
    unknown_fields: unknownFields,
  }
}

function blockedError(ruleId, path, message = '') {
  return { rule_id: ruleId, severity: 'blocked', passed: false, message, path }
}

function nearMatchField(path, suggestion, editDistance = 2) {
  return { path, classification: 'near_match', suggestion, edit_distance: editDistance }
}

// ── issueRegistry ────────────────────────────────────────────────────

describe('issueRegistry', () => {
  it('covers all known blocked rule_ids', () => {
    const knownRules = [
      'identity.invoice_number', 'identity.sender_name', 'identity.recipient_name',
      'items.non_empty', 'arithmetic.line_total', 'arithmetic.subtotal', 'arithmetic.total',
    ]
    for (const ruleId of knownRules) {
      expect(getIssueEntry(ruleId)).not.toBeNull()
    }
  })

  it('returns null for unknown rule_ids', () => {
    expect(getIssueEntry('unknown.rule')).toBeNull()
  })

  it('marks identity rules as non-diagnostic', () => {
    expect(ISSUE_REGISTRY['identity.invoice_number'].diagnosticOnly).toBe(false)
    expect(ISSUE_REGISTRY['identity.sender_name'].diagnosticOnly).toBe(false)
    expect(ISSUE_REGISTRY['identity.recipient_name'].diagnosticOnly).toBe(false)
  })

  it('marks arithmetic and items rules as diagnostic-only', () => {
    expect(ISSUE_REGISTRY['items.non_empty'].diagnosticOnly).toBe(true)
    expect(ISSUE_REGISTRY['arithmetic.total'].diagnosticOnly).toBe(true)
    expect(ISSUE_REGISTRY['arithmetic.subtotal'].diagnosticOnly).toBe(true)
    expect(ISSUE_REGISTRY['arithmetic.line_total'].diagnosticOnly).toBe(true)
  })
})

// ── resolveValueAtPath ───────────────────────────────────────────────

describe('resolveValueAtPath', () => {
  it('resolves top-level key', () => {
    expect(resolveValueAtPath({ invioce_number: 'INV-001' }, 'invioce_number')).toBe('INV-001')
  })

  it('resolves nested key', () => {
    expect(resolveValueAtPath({ sender: { company_nm: 'Acme' } }, 'sender.company_nm')).toBe('Acme')
  })

  it('returns undefined for missing key', () => {
    expect(resolveValueAtPath({ foo: 1 }, 'bar')).toBeUndefined()
  })

  it('returns undefined for missing nested parent', () => {
    expect(resolveValueAtPath({ foo: 1 }, 'sender.name')).toBeUndefined()
  })

  it('handles null/undefined input', () => {
    expect(resolveValueAtPath(null, 'foo')).toBeUndefined()
    expect(resolveValueAtPath(undefined, 'foo')).toBeUndefined()
  })

  it('resolves object values (for party renames)', () => {
    const obj = { recipeint: { name: 'Target LLC', email: 't@t.com' } }
    const val = resolveValueAtPath(obj, 'recipeint')
    expect(val).toEqual({ name: 'Target LLC', email: 't@t.com' })
  })
})

// ── setValueAtPath ──────────────────────────────────────────────────

describe('setValueAtPath', () => {
  it('sets top-level value', () => {
    const obj = { foo: 1 }
    setValueAtPath(obj, 'invoice_number', 'INV-001')
    expect(obj.invoice_number).toBe('INV-001')
  })

  it('sets nested value, creating intermediates', () => {
    const obj = {}
    setValueAtPath(obj, 'sender.name', 'Acme Corp')
    expect(obj.sender.name).toBe('Acme Corp')
  })

  it('sets nested value on existing parent', () => {
    const obj = { sender: { address: '123 Main St' } }
    setValueAtPath(obj, 'sender.name', 'Acme Corp')
    expect(obj.sender.name).toBe('Acme Corp')
    expect(obj.sender.address).toBe('123 Main St') // preserved
  })

  it('overwrites existing value', () => {
    const obj = { sender: { name: 'Old' } }
    setValueAtPath(obj, 'sender.name', 'New')
    expect(obj.sender.name).toBe('New')
  })

  it('handles deep paths with missing intermediates', () => {
    const obj = {}
    setValueAtPath(obj, 'a.b.c', 42)
    expect(obj.a.b.c).toBe(42)
  })
})

// ── renameKeyAtPath ─────────────────────────────────────────────────

describe('renameKeyAtPath', () => {
  it('renames a top-level key', () => {
    const obj = { invioce_number: 'INV-001', date: '2024-01-01' }
    renameKeyAtPath(obj, 'invioce_number', 'invoice_number')
    expect(obj.invoice_number).toBe('INV-001')
    expect('invioce_number' in obj).toBe(false)
    expect(obj.date).toBe('2024-01-01') // sibling preserved
  })

  it('preserves object values (for party renames)', () => {
    const obj = { recipeint: { name: 'Target', email: 't@t.com' }, total: 100 }
    renameKeyAtPath(obj, 'recipeint', 'recipient')
    expect(obj.recipient).toEqual({ name: 'Target', email: 't@t.com' })
    expect('recipeint' in obj).toBe(false)
    expect(obj.total).toBe(100)
  })

  it('no-ops when key does not exist', () => {
    const obj = { foo: 1 }
    renameKeyAtPath(obj, 'bar', 'baz')
    expect(obj).toEqual({ foo: 1 })
  })

  it('preserves insertion order', () => {
    const obj = { a: 1, old_key: 2, c: 3 }
    renameKeyAtPath(obj, 'old_key', 'new_key')
    expect(Object.keys(obj)).toEqual(['a', 'new_key', 'c'])
  })
})

// ── generatePatches: Tier classification ────────────────────────────

describe('generatePatches — classification', () => {
  it('identity.invoice_number with matching near_match → Tier A rename', () => {
    const raw = JSON.stringify({ invioce_number: 'INV-001', sender: { name: 'X' }, recipient: { name: 'Y' }, items: [{}] })
    const result = blockedResult({
      errors: [blockedError('identity.invoice_number', 'invoice_number')],
      unknownFields: [nearMatchField('invioce_number', 'invoice_number')],
    })
    const patches = generatePatches(result, raw)
    expect(patches).toHaveLength(1)
    expect(patches[0].tier).toBe('A')
    expect(patches[0].operation).toBe('rename')
    expect(patches[0].sourcePath).toBe('invioce_number')
    expect(patches[0].targetPath).toBe('invoice_number')
    expect(patches[0].value).toBe('INV-001')
  })

  it('identity.sender_name with no near_match → Tier B input', () => {
    const raw = JSON.stringify({ invoice_number: 'INV-001', items: [{}] })
    const result = blockedResult({
      errors: [blockedError('identity.sender_name', 'sender.name')],
      unknownFields: [],
    })
    const patches = generatePatches(result, raw)
    expect(patches).toHaveLength(1)
    expect(patches[0].tier).toBe('B')
    expect(patches[0].operation).toBe('set')
    expect(patches[0].targetPath).toBe('sender.name')
    expect(patches[0].inputRequired).toBe(true)
  })

  it('arithmetic.total → Tier C, no patches', () => {
    const raw = JSON.stringify({ total: 100 })
    const result = blockedResult({
      errors: [blockedError('arithmetic.total', 'total', 'total mismatch')],
    })
    const patches = generatePatches(result, raw)
    expect(patches).toHaveLength(0)
  })

  it('items.non_empty → Tier C, no patches', () => {
    const raw = JSON.stringify({ items: [] })
    const result = blockedResult({
      errors: [blockedError('items.non_empty', 'items')],
    })
    const patches = generatePatches(result, raw)
    expect(patches).toHaveLength(0)
  })

  it('parent-path match: recipeint → recipient (object with name child)', () => {
    const raw = JSON.stringify({
      invoice_number: 'INV-001',
      sender: { name: 'Acme' },
      recipeint: { name: 'Target LLC', email: 't@t.com' },
      items: [{}],
    })
    const result = blockedResult({
      errors: [blockedError('identity.recipient_name', 'recipient.name')],
      unknownFields: [nearMatchField('recipeint', 'recipient')],
    })
    const patches = generatePatches(result, raw)
    expect(patches).toHaveLength(1)
    expect(patches[0].tier).toBe('A')
    expect(patches[0].sourcePath).toBe('recipeint')
    expect(patches[0].targetPath).toBe('recipient')
  })

  it('parent-path match: typo value is string (no name child) → Tier B', () => {
    const raw = JSON.stringify({
      invoice_number: 'INV-001',
      sender: { name: 'Acme' },
      recipeint: 'Target LLC', // string, not object
      items: [{}],
    })
    const result = blockedResult({
      errors: [blockedError('identity.recipient_name', 'recipient.name')],
      unknownFields: [nearMatchField('recipeint', 'recipient')],
    })
    const patches = generatePatches(result, raw)
    expect(patches).toHaveLength(1)
    expect(patches[0].tier).toBe('B')
    expect(patches[0].operation).toBe('set')
  })

  it('nested near-match path (contains dot) is rejected → Tier B', () => {
    const raw = JSON.stringify({
      invoice_number: 'INV-001',
      sender: { companey_name: 'Acme' },
      items: [{}],
    })
    const result = blockedResult({
      errors: [blockedError('identity.sender_name', 'sender.name')],
      unknownFields: [nearMatchField('sender.companey_name', 'sender.name')],
    })
    const patches = generatePatches(result, raw)
    expect(patches).toHaveLength(1)
    expect(patches[0].tier).toBe('B') // not A — nested paths rejected in V1
  })
})

describe('generatePatches — mixed issues', () => {
  it('multiple blocked errors produce correct mix of Tier A and Tier B', () => {
    const raw = JSON.stringify({
      invioce_number: 'INV-001',
      recipeint: { name: 'Target', email: 't@t.com' },
      items: [{ description: 'Widget', quantity: 1, unit_price: 10, line_total: 10 }],
    })
    const result = blockedResult({
      errors: [
        blockedError('identity.invoice_number', 'invoice_number'),
        blockedError('identity.sender_name', 'sender.name'),
        blockedError('identity.recipient_name', 'recipient.name'),
      ],
      unknownFields: [
        nearMatchField('invioce_number', 'invoice_number'),
        nearMatchField('recipeint', 'recipient'),
      ],
    })
    const patches = generatePatches(result, raw)
    expect(patches).toHaveLength(3)

    const tierA = patches.filter(p => p.tier === 'A')
    const tierB = patches.filter(p => p.tier === 'B')
    expect(tierA).toHaveLength(2) // invoice_number rename + recipient rename
    expect(tierB).toHaveLength(1) // sender.name input
  })

  it('ready result returns no patches', () => {
    const result = { status: 'ready', render_ready: true, errors: [], unknown_fields: [] }
    expect(generatePatches(result, '{}')).toEqual([])
  })

  it('malformed JSON returns no patches', () => {
    const result = blockedResult({
      errors: [blockedError('identity.sender_name', 'sender.name')],
    })
    expect(generatePatches(result, '{ invalid json')).toEqual([])
  })
})

// ── applyPatches ────────────────────────────────────────────────────

describe('applyPatches', () => {
  it('applies rename to top-level key', () => {
    const json = JSON.stringify({ invioce_number: 'INV-001', date: '2024-01-01' }, null, 2)
    const patches = [{
      id: 'fix-0', tier: 'A', ruleId: 'identity.invoice_number',
      sourcePath: 'invioce_number', targetPath: 'invoice_number',
      operation: 'rename', value: 'INV-001', source: 'near_match',
      label: '', detail: '', status: 'accepted', inputRequired: false,
    }]
    const result = JSON.parse(applyPatches(json, patches))
    expect(result.invoice_number).toBe('INV-001')
    expect('invioce_number' in result).toBe(false)
    expect(result.date).toBe('2024-01-01')
  })

  it('applies set to create nested path', () => {
    const json = JSON.stringify({ invoice_number: 'INV-001' }, null, 2)
    const patches = [{
      id: 'fix-0', tier: 'B', ruleId: 'identity.sender_name',
      sourcePath: null, targetPath: 'sender.name',
      operation: 'set', value: 'Acme Corp', source: 'user_input',
      label: '', detail: '', status: 'accepted', inputRequired: true,
    }]
    const result = JSON.parse(applyPatches(json, patches))
    expect(result.sender.name).toBe('Acme Corp')
    expect(result.invoice_number).toBe('INV-001')
  })

  it('applies rename of nested object (preserves children)', () => {
    const json = JSON.stringify({
      recipeint: { name: 'Target', email: 't@t.com' },
      total: 100,
    }, null, 2)
    const patches = [{
      id: 'fix-0', tier: 'A', ruleId: 'identity.recipient_name',
      sourcePath: 'recipeint', targetPath: 'recipient',
      operation: 'rename', value: { name: 'Target', email: 't@t.com' },
      source: 'near_match', label: '', detail: '', status: 'accepted',
      inputRequired: false,
    }]
    const result = JSON.parse(applyPatches(json, patches))
    expect(result.recipient.name).toBe('Target')
    expect(result.recipient.email).toBe('t@t.com')
    expect('recipeint' in result).toBe(false)
  })

  it('ignores non-accepted patches', () => {
    const json = JSON.stringify({ invioce_number: 'INV-001' }, null, 2)
    const patches = [{
      id: 'fix-0', tier: 'A', ruleId: 'identity.invoice_number',
      sourcePath: 'invioce_number', targetPath: 'invoice_number',
      operation: 'rename', value: 'INV-001', source: 'near_match',
      label: '', detail: '', status: 'suggested', inputRequired: false,
    }]
    const result = JSON.parse(applyPatches(json, patches))
    expect('invioce_number' in result).toBe(true) // not renamed
  })

  it('preserves unrelated fields', () => {
    const json = JSON.stringify({
      invioce_number: 'INV-001',
      items: [{ description: 'Widget' }],
      notes: 'Hello',
    }, null, 2)
    const patches = [{
      id: 'fix-0', tier: 'A', ruleId: 'identity.invoice_number',
      sourcePath: 'invioce_number', targetPath: 'invoice_number',
      operation: 'rename', value: 'INV-001', source: 'near_match',
      label: '', detail: '', status: 'accepted', inputRequired: false,
    }]
    const result = JSON.parse(applyPatches(json, patches))
    expect(result.items[0].description).toBe('Widget')
    expect(result.notes).toBe('Hello')
  })

  it('applies renames before sets (ordering)', () => {
    // Rename selller → sender, then set sender.name
    const json = JSON.stringify({ selller: { email: 'a@b.com' } }, null, 2)
    const patches = [
      {
        id: 'fix-1', tier: 'B', ruleId: 'identity.sender_name',
        sourcePath: null, targetPath: 'sender.name',
        operation: 'set', value: 'Acme', source: 'user_input',
        label: '', detail: '', status: 'accepted', inputRequired: true,
      },
      {
        id: 'fix-0', tier: 'A', ruleId: 'some.other',
        sourcePath: 'selller', targetPath: 'sender',
        operation: 'rename', value: { email: 'a@b.com' },
        source: 'near_match', label: '', detail: '', status: 'accepted',
        inputRequired: false,
      },
    ]
    const result = JSON.parse(applyPatches(json, patches))
    expect(result.sender.name).toBe('Acme')
    expect(result.sender.email).toBe('a@b.com')
    expect('selller' in result).toBe(false)
  })

  it('returns unchanged JSON when no patches accepted', () => {
    const json = JSON.stringify({ foo: 1 }, null, 2)
    expect(applyPatches(json, [])).toBe(json)
  })
})

// ── computePatchDiff ────────────────────────────────────────────────

describe('computePatchDiff', () => {
  it('shows added and removed lines for a rename', () => {
    const original = JSON.stringify({ invioce_number: 'INV-001' }, null, 2)
    const patched = JSON.stringify({ invoice_number: 'INV-001' }, null, 2)
    const diff = computePatchDiff(original, patched)

    const removed = diff.filter(d => d.type === 'removed')
    const added = diff.filter(d => d.type === 'added')
    expect(removed.length).toBeGreaterThan(0)
    expect(added.length).toBeGreaterThan(0)
    expect(removed.some(d => d.text.includes('invioce_number'))).toBe(true)
    expect(added.some(d => d.text.includes('invoice_number'))).toBe(true)
  })

  it('shows added lines for a new field', () => {
    const original = JSON.stringify({ foo: 1 }, null, 2)
    const patched = JSON.stringify({ foo: 1, sender: { name: 'Acme' } }, null, 2)
    const diff = computePatchDiff(original, patched)

    const added = diff.filter(d => d.type === 'added')
    expect(added.length).toBeGreaterThan(0)
    expect(added.some(d => d.text.includes('sender'))).toBe(true)
  })

  it('returns empty array for invalid JSON', () => {
    expect(computePatchDiff('invalid', '{}')).toEqual([])
    expect(computePatchDiff('{}', 'invalid')).toEqual([])
  })

  it('returns all "same" lines for identical JSON', () => {
    const json = JSON.stringify({ a: 1, b: 2 }, null, 2)
    const diff = computePatchDiff(json, json)
    expect(diff.every(d => d.type === 'same')).toBe(true)
  })
})
