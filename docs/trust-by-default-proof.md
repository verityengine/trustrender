# Trust-by-Default Proof

Date: 2026-04-11
Test count: 620 (up from 592)

---

## What changed

Three moves that shift Formforge from "renderer with checks" to "trust layer for structured documents."

1. **Validation is now the default** for `.j2.typ` templates
2. **Include fragments are followed** in contract inference
3. **Semantic presets** cover invoices, receipts, and statements

---

## Proof 1: Bad payload fails before render by default

Before: `render("invoice.j2.typ", bad_data)` would crash with an opaque Jinja2 `UndefinedError` or silently render a broken document.

After: `render("invoice.j2.typ", bad_data)` raises `FormforgeError(code=DATA_CONTRACT)` with specific field paths before any Typst compilation starts.

```
$ formforge render examples/invoice.j2.typ bad_data.json -o out.pdf

error[DATA_CONTRACT]: 11 field errors in invoice.j2.typ
  stage: data_validation
  template: examples/invoice.j2.typ

  sender: missing required field (expected: object)
  recipient: missing required field (expected: object)
  items: missing required field (expected: list[object])
  ...
```

Opt-out: `formforge render ... --no-validate` or `render(..., validate=False)`.

**Tested by:** `test_validate_true_is_default` in test_contract.py

---

## Proof 2: Include-driven field requirement caught

Contract inference now follows `{% include %}` directives recursively.

Static includes: followed, fields merged into contract.
Dynamic includes (`{% include some_var %}`): marked partial.
Missing includes: marked partial, no crash.
Circular includes: cycle-detected, no infinite recursion.

```python
from formforge.contract import infer_contract_with_metadata

result = infer_contract_with_metadata("template_with_dynamic_include.j2.typ")
# result.is_partial == True
# result.unresolved_includes == ["<dynamic>"]
```

Preflight surfaces partial state:

```
Readiness: PASS (1 warning)
  warning: Contract is partial: include '<dynamic>' could not be resolved statically
```

**Tested by:** 10 tests in `TestIncludeInference`:
- static include with data field
- set variable not in contract
- without context isolation
- circular include safety
- dynamic include marks partial
- missing fragment marks partial
- ignore missing not partial
- nested includes followed
- invoice contract unchanged
- statement contract unchanged

---

## Proof 3: Receipt and statement semantic checks

### Receipt

`RECEIPT_HINTS` checks:
- Line item amounts sum to subtotal (arithmetic)
- Date is parseable
- Numeric fields are numeric (qty, unit_price, amount, subtotal, tax, total, tendered, change)
- receipt_number and company.name are non-empty

```python
from formforge.semantic import validate_semantics, RECEIPT_HINTS
report = validate_semantics(receipt_data, RECEIPT_HINTS)
# 0 issues on valid fixture data
# Arithmetic warning if subtotal doesn't match item sum
```

### Statement

`STATEMENT_HINTS` checks:
- Balance reconciliation: `opening_balance + total_charges + total_payments == closing_balance`
- Aging reconciliation: `aging.current + days_30 + days_60 + days_90 == aging.total`
- Date parseable
- Numeric fields parseable (all balance/aging fields)
- customer.name and account_number non-empty

```python
from formforge.semantic import validate_semantics, STATEMENT_HINTS
report = validate_semantics(statement_data, STATEMENT_HINTS)
# 0 issues on valid fixture data
# Arithmetic warning if aging totals don't sum
# Arithmetic warning if balance equation doesn't hold
```

### Auto-detection

CLI auto-detects template type from filename:
- `*invoice*` / `*einvoice*` -> INVOICE_HINTS
- `*receipt*` -> RECEIPT_HINTS
- `*statement*` -> STATEMENT_HINTS
- everything else -> None (with warning: "no semantic hints configured")

No fake confidence for unknown templates.

**Tested by:** 17 tests across `TestReceiptHints`, `TestStatementHints`, `TestReconciliation`, `TestHintAutoDetection`

---

## API surface changes

| Surface | Before | After |
|---|---|---|
| `render()` | `validate=False` | `validate=True` |
| `audit()` | `validate=False` | `validate=True` |
| Server POST /render | `"validate"` defaults False | `"validate"` defaults True |
| CLI `formforge render` | `--validate` flag | `--no-validate` flag |
| Contract inference | Skips includes | Follows includes recursively |
| `infer_contract()` | Returns DataContract | Returns DataContract (unchanged) |
| `infer_contract_with_metadata()` | N/A (new) | Returns InferenceResult with is_partial |
| Semantic presets | INVOICE_HINTS only | INVOICE_HINTS, RECEIPT_HINTS, STATEMENT_HINTS |
| SemanticHints | 5 fields | 6 fields (+reconciliations) |
| validate_semantics checks | 4 | 5 (+balance_reconciliation) |

---

## Files modified

- `src/formforge/__init__.py` — validate defaults
- `src/formforge/server.py` — server validate default
- `src/formforge/cli.py` — --no-validate flag, _resolve_hints(), infer_contract_with_metadata usage
- `src/formforge/contract.py` — InferenceResult, infer_contract_with_metadata(), _visit_Include implementation
- `src/formforge/semantic.py` — RECEIPT_HINTS, STATEMENT_HINTS, reconciliations field, _check_reconciliation()
- `src/formforge/readiness.py` — partial contract warnings in preflight
- `tests/test_contract.py` — 11 new tests (1 default-validation + 10 include inference)
- `tests/test_semantic.py` — 17 new tests (receipt, statement, reconciliation, auto-detection)
- `tests/test_error_pipeline.py` — 3 tests updated (explicit validate=False)
- `tests/test_audit_e2e.py` — 1 test updated (5 checks, not 4)
- `CLAUDE.md` — updated product truth
