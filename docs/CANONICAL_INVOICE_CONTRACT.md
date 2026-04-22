# Canonical Invoice Contract

Reference for the TrustRender invoice ingestion pipeline.
Defines the canonical schema, render-ready requirements, and downstream expectations.

## Canonical Schema

Every invoice payload, regardless of source vendor or field naming convention,
is normalized to this shape by the ingest layer (`invoice_ingest.py`):

```
invoice_number    str       (required)
invoice_date      str       YYYY-MM-DD
due_date          str       YYYY-MM-DD
sender            Address   { name, address, email }
recipient         Address   { name, address, email }
items             Item[]    [{ num, description, quantity, unit_price, line_total, tax_rate }]
subtotal          float
tax_rate          float
tax_amount        float
total             float
currency          str       default "USD"
payment_terms     str
notes             str
extras            dict      unrecognized fields preserved here
```

Party sub-fields (`sender`, `recipient`):
- `name` (str, required for render-ready)
- `address` (str)
- `email` (str)

## Render-Ready Requirements

A payload is **render-ready** when all of these pass:

| Rule ID                  | Condition                                          |
|--------------------------|-----------------------------------------------------|
| `identity.invoice_number`| `invoice_number` is non-empty                       |
| `identity.sender_name`   | `sender.name` is non-empty                          |
| `identity.recipient_name`| `recipient.name` is non-empty                       |
| `items.non_empty`        | `items` has at least 1 entry                        |
| `arithmetic.line_total`  | Each item: `line_total == quantity * unit_price`     |
| `arithmetic.subtotal`    | `subtotal == sum(line_totals)`                      |
| `arithmetic.total`       | `total == subtotal + tax_amount`                    |

Arithmetic checks only fire when both sides are non-zero (computed defaults are exempt).

## Blocked Conditions

Any rule above failing with `severity: blocked` prevents rendering.
`template_payload` is set to `None` when blocked — this is intentional
to prevent accidental downstream use of incomplete data.

## Template Inference

Deterministic, based on canonical shape only:

```
if invoice_number present AND items is non-empty array:
    -> invoice.j2.typ
else:
    -> null (user must select manually)
```

No vendor detection. No heuristics. Extend this function when new
document types (receipt, statement, etc.) gain ingest support.

## Template Payload

When render-ready, `template_payload` is produced by `to_template_shape()`:
- Amounts formatted as display strings (`$4,500.00`)
- Dates formatted as display strings (`April 10, 2026`)
- Items keyed as `num`, `description`, `qty`, `unit_price`, `amount`

This is the object that flows into the Typst template at render time.

## Downstream Consumers

All paths downstream of ingest MUST consume canonical field names:

| Path              | Consumes            | Status   |
|-------------------|---------------------|----------|
| Preflight         | canonical schema    | Clean    |
| invoice.j2.typ    | template_payload    | Clean    |
| UI summary view   | canonical + payload | Clean    |
| UI handoff        | template_payload    | Clean    |
| ZUGFeRD/e-invoice | seller/buyer        | **WRONG** |

### Known Issue: ZUGFeRD Schema Leak

`zugferd.py` and `einvoice.j2.typ` expect `seller`/`buyer` instead of
canonical `sender`/`recipient`. This creates a parallel contract outside
the canonical pipeline. Future fix: e-invoice layer should adapt FROM
canonical, not demand alternate upstream field names.

## Alias Resolution

Vendor-specific field names are resolved in `invoice_aliases.py`.
Four scoped maps:
- `TOP_LEVEL_ALIASES` — top-level field names
- `FLAT_SENDER_FIELDS` / `FLAT_RECIPIENT_FIELDS` — flat party synthesis
- `PARTY_ALIASES` — party sub-field names
- `ITEM_ALIASES` — line item sub-field names

Aliases are exact-match lookups, never fuzzy. Near-match detection
(difflib, cutoff 0.8) provides suggestions only — never auto-maps.

## Test Coverage

| Suite                        | Count | What it proves                              |
|------------------------------|-------|---------------------------------------------|
| `test_invoice_ingest.py`     | 52    | Core pipeline logic, edge cases             |
| `test_real_payloads.py`      | 6     | Named vendor fixtures (Stripe, QBO, etc.)   |
| `test_adversarial_corpus.py` | 34    | Unseen payloads, generalization proof        |
| `workspace.spec.js`          | 40    | Browser UI, state model, recovery           |
