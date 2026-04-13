/**
 * Patch utilities for guided blocked-issue resolution.
 *
 * Pure functions — no React, no DOM, no side effects.
 * All patch logic lives here so it can be unit-tested
 * independently of App.jsx.
 *
 * Key concepts:
 *   - Patches describe mutations to the raw source JSON.
 *   - Tier A patches are deterministic renames (near-match typos).
 *   - Tier B patches are user-supplied values (missing required fields).
 *   - Tier C issues get no patch — diagnostic only.
 *   - Patches are applied client-side, then ingest is rerun through
 *     the full pipeline. The backend never sees patch objects.
 */

import { ISSUE_REGISTRY } from './issueRegistry.js'

// ── Path helpers ────────────────────────────────────────────────────

/**
 * Read a value from an object at a dotted key path.
 * Supports top-level keys and one level of nesting.
 * Returns undefined if the path cannot be resolved.
 *
 * Examples:
 *   resolveValueAtPath(obj, "invioce_number")       → obj["invioce_number"]
 *   resolveValueAtPath(obj, "sender.company_nm")     → obj?.sender?.["company_nm"]
 */
export function resolveValueAtPath(obj, keyPath) {
  if (!obj || typeof obj !== 'object') return undefined
  const parts = keyPath.split('.')
  let current = obj
  for (const part of parts) {
    if (current == null || typeof current !== 'object') return undefined
    current = current[part]
  }
  return current
}

/**
 * Set a value at a dotted path, creating intermediate objects if needed.
 * Mutates obj in place.
 *
 * Examples:
 *   setValueAtPath(obj, "invoice_number", "INV-001")
 *   setValueAtPath(obj, "sender.name", "Acme Corp")  // creates sender: {} if missing
 */
export function setValueAtPath(obj, dottedPath, value) {
  const parts = dottedPath.split('.')
  let current = obj
  for (let i = 0; i < parts.length - 1; i++) {
    const key = parts[i]
    if (current[key] == null || typeof current[key] !== 'object') {
      current[key] = {}
    }
    current = current[key]
  }
  current[parts[parts.length - 1]] = value
}

/**
 * Rename a top-level key in an object, preserving value and sibling order.
 * Mutates obj in place. Top-level only — V1 constraint.
 *
 * Example:
 *   renameKeyAtPath(obj, "invioce_number", "invoice_number")
 */
export function renameKeyAtPath(obj, fromKey, toKey) {
  if (!(fromKey in obj)) return
  // Rebuild the object to preserve insertion order with the new key
  const entries = Object.entries(obj)
  // Clear all keys
  for (const key of Object.keys(obj)) delete obj[key]
  // Re-insert with rename applied
  for (const [key, value] of entries) {
    obj[key === fromKey ? toKey : key] = value
  }
}

// ── Patch generation ────────────────────────────────────────────────

/**
 * Generate patches for all blocked issues in an ingest result.
 *
 * @param {object} ingestResult - Full ingest response from /ingest
 * @param {string} rawJsonString - Current raw JSON from the editor
 * @returns {Array} Array of Patch objects
 */
export function generatePatches(ingestResult, rawJsonString) {
  if (!ingestResult || ingestResult.render_ready) return []

  const blockedErrors = (ingestResult.errors || []).filter(
    e => e.severity === 'blocked'
  )
  if (blockedErrors.length === 0) return []

  const unknownFields = ingestResult.unknown_fields || []
  let sourceObj
  try {
    sourceObj = JSON.parse(rawJsonString)
  } catch {
    return [] // can't generate patches if JSON is malformed
  }

  const patches = []
  let patchIndex = 0

  for (const error of blockedErrors) {
    const entry = ISSUE_REGISTRY[error.rule_id]
    if (!entry || entry.diagnosticOnly) continue // Tier C — no patch

    // Try Tier A: look for a near-match in unknown_fields
    const tierAPatch = tryTierA(error, entry, unknownFields, sourceObj, patchIndex)
    if (tierAPatch) {
      patches.push(tierAPatch)
      patchIndex++
      continue
    }

    // Fall through to Tier B: user must supply value
    patches.push({
      id: `fix-${error.rule_id}-${patchIndex}`,
      tier: 'B',
      ruleId: error.rule_id,
      sourcePath: null,
      targetPath: entry.blockedPath,
      operation: 'set',
      value: null,
      source: 'user_input',
      label: entry.inputLabel,
      detail: `Supply a value for ${entry.blockedPath}`,
      status: 'suggested',
      inputRequired: true,
    })
    patchIndex++
  }

  return patches
}

/**
 * Try to create a Tier A (deterministic rename) patch for a blocked error.
 *
 * Returns a Patch object if a valid near-match is found, or null.
 *
 * Rules (V1 — intentionally narrow):
 *   1. Only top-level key renames.
 *   2. The unknown_field must have classification === "near_match".
 *   3. The suggestion must match the blocked path directly OR match the
 *      parent path (e.g., suggestion "sender" for blocked "sender.name").
 *   4. For parent-path matches: the value at the typo key must be an
 *      object containing a "name" child. Otherwise → Tier B.
 *   5. The value must actually exist at the source path in rawJson.
 */
function tryTierA(error, entry, unknownFields, sourceObj, patchIndex) {
  const nearMatches = unknownFields.filter(u => u.classification === 'near_match')
  if (nearMatches.length === 0) return null

  // Direct match: suggestion === blockedPath (e.g., "invoice_number")
  let candidate = nearMatches.find(u => u.suggestion === entry.blockedPath)

  // Parent match: suggestion === parentPath (e.g., "sender" for blocked "sender.name")
  if (!candidate && entry.parentPath) {
    candidate = nearMatches.find(u => u.suggestion === entry.parentPath)
  }

  if (!candidate) return null

  // V1 constraint: top-level keys only — the path must not contain dots
  if (candidate.path.includes('.')) return null

  // Read the actual value from the source JSON
  const value = resolveValueAtPath(sourceObj, candidate.path)
  if (value === undefined) return null

  // For parent-path matches: value must be an object with a "name" child
  if (candidate.suggestion === entry.parentPath) {
    if (typeof value !== 'object' || value === null || !('name' in value)) {
      return null // not safe — fall through to Tier B
    }
  }

  const targetKey = candidate.suggestion
  return {
    id: `fix-${error.rule_id}-${patchIndex}`,
    tier: 'A',
    ruleId: error.rule_id,
    sourcePath: candidate.path,
    targetPath: targetKey,
    operation: 'rename',
    value, // for preview display
    source: 'near_match',
    label: `Rename "${candidate.path}" \u2192 "${targetKey}"`,
    detail: `Near-match detected (edit distance ${candidate.edit_distance || '?'})`,
    status: 'suggested',
    inputRequired: false,
  }
}

// ── Patch application ───────────────────────────────────────────────

/**
 * Apply accepted patches to a raw JSON string.
 * Returns a new JSON string with patches applied.
 *
 * Order: renames first, then sets. This ensures that a set to
 * "sender.name" works even if "sender" was just renamed from a typo.
 *
 * @param {string} jsonString - Raw JSON from the editor
 * @param {Array} patches - Array of Patch objects (only accepted ones are applied)
 * @returns {string} New JSON string
 */
export function applyPatches(jsonString, patches) {
  const accepted = patches.filter(p => p.status === 'accepted')
  if (accepted.length === 0) return jsonString

  const obj = JSON.parse(jsonString)

  // Sort: renames before sets
  const sorted = [...accepted].sort((a, b) => {
    if (a.operation === 'rename' && b.operation !== 'rename') return -1
    if (a.operation !== 'rename' && b.operation === 'rename') return 1
    return 0
  })

  for (const patch of sorted) {
    if (patch.operation === 'rename') {
      renameKeyAtPath(obj, patch.sourcePath, patch.targetPath)
    } else if (patch.operation === 'set') {
      setValueAtPath(obj, patch.targetPath, patch.value)
    }
  }

  return JSON.stringify(obj, null, 2)
}

// ── Diff preview ────────────────────────────────────────────────────

/**
 * Compute a line-by-line diff between two JSON strings.
 * Both inputs are re-parsed and re-stringified with the same formatter
 * to avoid false diffs from whitespace differences.
 *
 * Returns an array of { type, text } objects where type is
 * 'same', 'added', or 'removed'.
 */
export function computePatchDiff(originalJson, patchedJson) {
  // Normalize formatting
  let origLines, patchedLines
  try {
    origLines = JSON.stringify(JSON.parse(originalJson), null, 2).split('\n')
    patchedLines = JSON.stringify(JSON.parse(patchedJson), null, 2).split('\n')
  } catch {
    return []
  }

  // Simple line-by-line diff (not LCS — good enough for small JSON patches)
  const result = []
  const maxLen = Math.max(origLines.length, patchedLines.length)

  // Build a set-based diff for better accuracy
  const origSet = new Map()
  for (const line of origLines) {
    origSet.set(line, (origSet.get(line) || 0) + 1)
  }
  const patchedSet = new Map()
  for (const line of patchedLines) {
    patchedSet.set(line, (patchedSet.get(line) || 0) + 1)
  }

  // Use a simple LCS-like approach: walk both arrays
  let i = 0, j = 0
  while (i < origLines.length || j < patchedLines.length) {
    if (i < origLines.length && j < patchedLines.length && origLines[i] === patchedLines[j]) {
      result.push({ type: 'same', text: origLines[i] })
      i++
      j++
    } else {
      // Check if the current original line appears later in patched
      const origLineInPatched = patchedLines.indexOf(origLines[i], j)
      const patchedLineInOrig = origLines.indexOf(patchedLines[j], i)

      if (i < origLines.length && (origLineInPatched === -1 || (patchedLineInOrig !== -1 && patchedLineInOrig <= origLineInPatched))) {
        result.push({ type: 'removed', text: origLines[i] })
        i++
      } else if (j < patchedLines.length) {
        result.push({ type: 'added', text: patchedLines[j] })
        j++
      } else {
        break
      }
    }
  }

  return result
}
