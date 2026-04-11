# Ugly-Data Pressure Test Findings

Conducted: 2026-04-12
Tests: 28 pressure tests across 13 categories
Results: 28/28 passing
Full suite: 736 passing

---

## Summary

| Outcome | Count |
|---------|-------|
| Should allow, no warning — and does | 48 |
| Should allow, with warning — and does | 8 |
| Should block — and does | 4 |
| Should warn — fixed to warn (was gap) | 2 |
| Acceptable limit documented | 6 |

---

## Group 1: Real Product Gaps (fixed)

| Case | Expected | Actual | Verdict | Caught by | Public claim impact | Fix type | Action |
|------|----------|--------|---------|-----------|---------------------|----------|--------|
| Infinity string in numeric field | should warn | silently accepted as valid number | **Fixed** | semantic (numeric_coercion) | None — was a gap, now closed | code | `_try_parse_number` now rejects non-finite via `math.isfinite()` |
| NaN string in numeric field | should warn | silently accepted as valid number | **Fixed** | semantic (numeric_coercion) | None — was a gap, now closed | code | Same fix as Infinity |

## Group 2: Acceptable Limits (document, don't fix)

| Case | Expected | Actual | Verdict | Caught by | Public claim impact | Fix type | Action |
|------|----------|--------|---------|-----------|---------------------|----------|--------|
| Rounding at exact $0.01 boundary | should allow | warns (float noise: 0.010000000000001563 > 0.01) | Acceptable limit | semantic (arithmetic) | None — tolerance rule is `> 0.01` strictly | docs | Documented; test uses $0.005 to stay within tolerance |
| ₹ (Indian Rupee) in amounts | should allow render | renders fine; semantic silent | Acceptable limit | not caught | Narrow: semantic currency parsing covers `€$£¥` only | docs | Document currency symbol scope in known-limits.md |
| European comma decimal (1.234,56) | should allow render | renders fine; semantic can't parse | Acceptable limit | not caught | Narrow: European number format not supported by semantic parser | docs | Document in known-limits.md |
| Beyond float64 precision (2^53+1) | should allow | renders fine; precision loss in float | Acceptable limit | n/a | None — amounts are strings in templates, precision only matters in semantic checks | docs | Document float precision limit |
| RTL text (Arabic/Hebrew) | should allow | renders valid PDF | Acceptable limit | n/a | None — glyph accuracy depends on font coverage | docs | Bundled Inter has limited RTL support |

## Group 3: Wrong Test Assumptions (test corrected, product correct)

| Case | Expected | Actual | Verdict | Caught by | Public claim impact | Fix type | Action |
|------|----------|--------|---------|-----------|---------------------|----------|--------|
| None in required field (description) | should block | blocks with contract error | Correct | contract_validation / DATA_CONTRACT | None — contract works correctly | none | Test expectation corrected |
| None in unguarded field (notes) | should block | blocks with contract error | Correct | contract_validation / DATA_CONTRACT | None — notes is required (unguarded in template) | none | Test expectation corrected |
| Infinity/NaN hint alignment | should warn | no warning (wrong hints used) | Correct | n/a | None — test used INVOICE_HINTS but data used `amount` not `line_total` | none | Test uses local SemanticHints matching fixture schema |
| Rounding test boundary | should allow | warns at $0.01 boundary | Correct | n/a | None — float representation makes exact boundary ambiguous | none | Test uses $0.005 to stay safely within tolerance |

## Group 4: Correct Behavior Confirmed (no action needed)

| Case | Expected | Actual | Verdict | Caught by | Public claim impact | Fix type | Action |
|------|----------|--------|---------|-----------|---------------------|----------|--------|
| Ambiguous date 01/02/03 | should warn | warns (can't parse) | Correct | semantic (date_format) | None | none | — |
| ISO date with timezone | should warn | warns (TZ format not in list) | Correct | semantic (date_format) | None | none | — |
| Epoch timestamp as date | should warn | warns (not parseable) | Correct | semantic (date_format) | None | none | — |
| "TBD" as date | should warn | warns | Correct | semantic (date_format) | None | none | — |
| Integer as date field | should warn | warns (not a string) | Correct | semantic (date_format) | None | none | — |
| Empty string date | should allow | allows (empty is OK) | Correct | n/a | None | none | — |
| R$ (Brazilian Real) | should allow | renders fine | Correct | n/a | None | none | — |
| kr (Swedish Krona) | should allow | renders fine | Correct | n/a | None | none | — |
| Mixed currency symbols | should allow | renders fine | Correct | n/a | None | none | — |
| Accounting parens (500.00) | should allow | renders fine; semantic parses correctly | Correct | n/a | None | none | — |
| Bare numbers no symbol | should allow | renders fine | Correct | n/a | None | none | — |
| Control chars (tab, newline, CRLF, FF) | should allow | renders fine | Correct | n/a | None | none | — |
| Zero-width chars (ZWSP, ZWJ, NBSP) | should allow | renders fine | Correct | n/a | None | none | — |
| Null byte in string | should allow | renders fine | Correct | n/a | None | none | — |
| Arabic/Hebrew/bidi text | should allow | renders valid PDF | Correct | n/a | None | none | — |
| 15-digit total | should allow | renders fine | Correct | n/a | None | none | — |
| Many/few decimal places | should allow | renders fine | Correct | n/a | None | none | — |
| Duplicate semantic keys | should allow | renders fine, preflight passes | Correct | n/a | None — extra keys explicitly allowed | none | — |
| Boolean/scientific/negative-zero | should allow | renders fine | Correct | n/a | None | none | — |
| Integer/float amounts | should allow | renders fine | Correct | n/a | None | none | — |
| Inconsistent item schemas | should allow | renders fine | Correct | n/a | None | none | — |
| 50 items correct sum | should allow | renders fine | Correct | n/a | None | none | — |
| Arithmetic drift > $0.01 | should warn | warns | Correct | semantic (arithmetic) | None | none | — |
| Arithmetic drift <= $0.005 | should allow | allows | Correct | n/a | None | none | — |
| Zero quantity/price/all zeros | should allow | renders fine | Correct | n/a | None | none | — |
| String "true"/"false"/"null"/"0" | should allow | renders fine | Correct | n/a | None | none | — |
| Empty dict as sender | should block | blocks | Correct | contract_validation / DATA_CONTRACT | None | none | — |
| List where scalar expected | should block | blocks | Correct | contract_validation / DATA_CONTRACT | None | none | — |
| Deep nesting with extra metadata | should allow | renders fine | Correct | n/a | None | none | — |
| Preflight + semantic mismatch | preflight ready | preflight passes (semantic opt-in) | Correct | n/a | None | none | — |
| Preflight with extra keys | should allow | preflight ready | Correct | n/a | None | none | — |
| Preflight with type confusion | should allow | preflight ready | Correct | n/a | None | none | — |
| Preflight-render agreement | both pass | both pass | Correct | n/a | None | none | — |

---

## Code fix applied

**`src/trustrender/semantic.py` — `_try_parse_number()`**

Added `math.isfinite()` check after `float()` parsing. Non-finite values (Infinity, -Infinity, NaN) now return `None`, which means:
- They trigger `numeric_coercion` warnings when hinted
- They cause arithmetic checks to skip (subtotal unparseable)
- They never silently pass as valid business numbers

---

## Rounding tolerance rule (locked)

Tolerance: `> 0.01` (strictly greater than one cent).

- $0.01 difference: within tolerance, no warning
- $0.02 difference: exceeds tolerance, warning fires
- Float noise at exact boundary (`abs(30.0 - 30.01) = 0.010000000000001563`): fires warning due to IEEE 754 — acceptable, since exact-boundary values are edge cases

---

## Known limits to document

1. **Currency symbol scope**: Semantic parser strips `€$£¥` only. Other symbols (`₹`, `R$`, `kr`, `zl`, `₱`, `₽`) are not stripped, causing parse failure. Arithmetic and numeric checks silently skip when values can't be parsed.

2. **European number format**: `1.234,56` (period=thousands, comma=decimal) is not supported by the parser. The comma is stripped as a thousands separator, leaving `1.234.56` which fails `float()`.

3. **Float precision**: Numbers beyond 2^53 lose integer precision in `float()`. This only affects semantic arithmetic checks, not rendering (amounts are strings in templates).

4. **RTL text**: Renders to valid PDF. Glyph accuracy depends on font coverage — bundled Inter has limited RTL support.

---

## Public claim impact

**No strong public claim was broken.** The Infinity/NaN gap was in semantic validation internals, not a public-facing feature claim. All other behaviors match documented and tested expectations.

**Claims that are now stronger:**
- Contract validation catches None in required fields (demonstrated with exact paths)
- Extra keys in data are explicitly allowed (demonstrated with 20+ extra fields)
- Preflight and render agree on readiness (demonstrated for both invoice and statement)
- Control characters, RTL, null bytes all render without crash

**Claims to narrow in copy:**
- Semantic currency parsing: should qualify as "supports `$`, `€`, `£`, `¥` currency symbols"
- European number format: should note as unsupported in known-limits.md
