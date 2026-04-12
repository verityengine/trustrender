# Validation & Readiness

TrustRender validates data at multiple levels before rendering.

## Structural validation (default)

Every `render()` call on a `.j2.typ` template infers a minimum data contract from the Jinja2 AST and validates caller data against it. This catches:

- missing required fields
- null values on required fields
- wrong structural types (passing a string where an object is expected, a dict where a list is expected)
- requirements from `{% include %}` fragments (followed recursively with scope isolation)

Bad data raises `TrustRenderError(code=DATA_CONTRACT)` with paths pointing into the caller's JSON:

```python
render("invoice.j2.typ", {"invoice_number": "X"})
```

```
TrustRenderError: Data validation failed: 11 field errors in invoice.j2.typ
  sender: missing required field (expected: object)
  recipient: missing required field (expected: object)
  items: missing required field (expected: list[object])
  invoice_date: missing required field
  ...
```

To skip: `render(..., validate=False)` or `trustrender render ... --no-validate`.

## Semantic validation (opt-in)

Beyond structure, TrustRender checks business-data correctness when semantic hints are configured. Semantic checks warn but do not block rendering.

What it catches:

- **Arithmetic mismatches**: line item totals that don't sum to the stated subtotal
- **Balance reconciliation**: aging bucket totals that don't sum to the closing balance
- **Unparseable dates**: strings in date fields that don't match any common format
- **Non-numeric values**: currency fields containing non-parseable text
- **Empty required fields**: business-critical fields that are blank strings or None

```python
from trustrender.semantic import validate_semantics, STATEMENT_HINTS

report = validate_semantics(statement_data, STATEMENT_HINTS)
```

### Presets

| Preset | Checks |
|--------|--------|
| `INVOICE_HINTS` | line item sum, dates, numerics, invoice number, text anomalies |
| `RECEIPT_HINTS` | item amounts, subtotal, dates, numerics, text anomalies |
| `STATEMENT_HINTS` | balance reconciliation, aging totals, dates, numerics, text anomalies |
| `LETTER_HINTS` | date, sender/recipient names, subject, closing, text anomalies |
| `REPORT_HINTS` | date, title, company name, executive summary, spend numerics, text anomalies |

The CLI auto-detects the preset from the template filename. Unknown template types get no semantic checks — no fake confidence.

## Readiness (preflight)

`preflight()` combines structural validation, semantic checks, template parsing, environment checks, and compliance eligibility into a single pre-render verdict:

```python
from trustrender.readiness import preflight
from trustrender.semantic import INVOICE_HINTS

verdict = preflight("invoice.j2.typ", data, semantic_hints=INVOICE_HINTS)
if not verdict.ready:
    for issue in verdict.errors:
        print(f"{issue.path}: {issue.message}")
```

```
trustrender preflight invoice.j2.typ data.json --semantic
```

Preflight includes a `text_safety` stage that scans all string values for control characters and zero-width characters — no semantic hints required. Set `text_scan=False` to opt out.

With `strict=True`, partial contracts from unresolved dynamic includes are promoted from warnings to errors.

## Include behavior

Contract inference follows `{% include %}` directives recursively. Static includes are resolved and their data requirements merged into the parent contract. Variables set via `{% set %}` in the parent scope are excluded.

Dynamic includes (`{% include some_var %}`) cannot be resolved statically. They mark the contract as partial — visible via `infer_contract_with_metadata()` and as a warning in `trustrender check` output.

## Inspecting contracts

```
trustrender check examples/invoice.j2.typ
```

```
Template: examples/invoice.j2.typ
Fields: 12 top-level (12 required)

  * sender: object {address, email, name}
  * recipient: object {address, email, name}
  * items: list[{amount, description, num, qty, unit_price}]
  * invoice_number: scalar
  ...
```

With data validation: `trustrender check examples/invoice.j2.typ --data bad_data.json`

## Limits

- Structural types only (scalar / object / list) — no int/str/float narrowing
- `required` is a template-read heuristic, not business-semantic truth
- Semantic checks require explicit hints — no automatic business-logic inference
- Dynamic `{% include %}` produces a partial contract (warning by default; use `strict=True` to block)
- Numeric coercion is intentionally narrow — locale-specific money formats should be normalized upstream
