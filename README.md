# TrustRender

Validate and normalize billing data from Stripe, Shopify, and custom systems before Factur-X/ZUGFeRD embedding.

If you're bridging a non-compliant billing platform into EU e-invoicing, TrustRender adds a validation and normalization layer before tools like [factur-x](https://github.com/akretion/factur-x) and [drafthorse](https://github.com/pretix/python-drafthorse) generate or embed compliant XML. It catches arithmetic mismatches, field misalignment, missing required fields, and structural problems before handoff.

```
pip install trustrender
trustrender validate invoice.json
```

## What it does

Takes invoice JSON from Stripe, Shopify, custom billing APIs, or legacy exports and tells you whether it's safe to embed as Factur-X/ZUGFeRD.

```
$ trustrender validate quickbooks_invoice.json

Invoice:   INV-2026-5541
From:      Summit Analytics Co.
To:        Horizon Financial
Items:     2
Total:     $10,524.50

Normalizations (25):
  DocNumber → invoice_number        CompanyName → sender.name
  TxnDate → invoice_date            customer.Name → recipient.name
  Line → items                      SubTotal → subtotal
  ... and 19 more

PASS — invoice data is valid

Safe to embed in Factur-X/ZUGFeRD PDF.
```

Bad data gets blocked:

```
$ trustrender validate ocr_extracted_invoice.json

BLOCKED — 2 problem(s)

  items[1] total is wrong
    You entered $459.00 but math says $450.00
    Fix the line total or the price/quantity.

  Subtotal is wrong
    Lines add up to $12,459.00 but you listed $12,450.00

This invoice cannot be processed until the problems above are fixed.
```

## Install

```
pip install trustrender
```

Core install requires only `drafthorse`. No Typst, no browser, no heavy deps.

Optional extras:
```
pip install "trustrender[zugferd]"    # XSD/Schematron validation
pip install "trustrender[render]"     # PDF rendering via Typst
pip install "trustrender[all]"        # everything
```

Requires Python 3.11+.

## Python API

```python
from trustrender import validate_invoice

result = validate_invoice({
    "invoiceNo": "INV-001",
    "vendor": {"companyName": "Acme Corp"},
    "customer": {"Name": "Client Inc"},
    "LineItems": [{"desc": "Widget", "qty": 2, "unitPrice": 50, "amount": 100}],
    "SubTotal": 100,
    "tax": 8.50,
    "TotalAmt": 108.50,
}, zugferd=True)

if result["render_ready"] and result.get("zugferd_ready"):
    # safe to call factur-x / drafthorse
    print("All checks passed")
else:
    for error in result["errors"]:
        print(f"BLOCKED: {error['message']}")
```

`validate_invoice()` returns:
- `status`: "ready" | "ready_with_warnings" | "blocked"
- `render_ready`: bool
- `canonical`: normalized invoice dict (all fields in canonical names)
- `errors`: list of blocking issues with rule_id, path, expected/actual
- `warnings`: advisory issues
- `normalizations`: field-level provenance (what was renamed, coerced, computed)
- `zugferd_ready`: bool (if `zugferd=True`)

## Stripe adapter

Raw Stripe Invoice API responses use cents, Unix timestamps, and nested structures. The adapter handles all of it:

```bash
trustrender validate stripe_invoice.json --source stripe --zugferd
```

```python
from trustrender import validate_invoice
from trustrender.adapters import from_stripe

result = validate_invoice(from_stripe(raw_stripe_response), zugferd=True)
```

The adapter converts cents to dollars, timestamps to dates, extracts line items from `lines.data[]`, and maps customer fields to recipient. Seller info is not included in Stripe invoices — TrustRender will flag it if required for ZUGFeRD compliance.

## Shopify adapter

Shopify orders use decimal strings, split customer names, and a different structure from invoices:

```bash
trustrender validate shopify_order.json --source shopify
```

```python
from trustrender import validate_invoice
from trustrender.adapters import from_shopify

result = validate_invoice(from_shopify(raw_shopify_order))
```

The adapter parses string amounts to floats, combines first_name + last_name, maps order fields to invoice structure, and preserves structured address fields. Shopify orders have no seller info or due date — TrustRender handles both correctly.

## What it normalizes

90+ vendor field aliases across QuickBooks, Xero, Stripe, and generic CSV/ERP formats:

| Source field | Canonical field |
|---|---|
| `DocNumber`, `invoiceNo`, `inv_no`, `ref` | `invoice_number` |
| `CompanyName`, `account_name`, `bill_from_name` | `sender.name` |
| `customer`, `billTo`, `Contact` | `recipient` |
| `Line`, `LineItems`, `entries`, `products` | `items` |
| `UnitPrice`, `cost`, `rate`, `unitCost` | `unit_price` |
| `Amount`, `LineAmount`, `line_total` | `line_total` |
| `SubTotal`, `net_total`, `sub_total` | `subtotal` |
| `TotalAmt`, `grand_total`, `amount_due` | `total` |

Plus: type coercion (`"$1,234.56"` → `1234.56`), date parsing (`"April 10, 2026"` → `2026-04-10`), computed defaults (missing `line_total` = `qty × price`), near-match typo detection (`invioce_number` → suggests `invoice_number`).

## What it checks

7 deterministic semantic checks, all arithmetic:

| Check | What it catches |
|---|---|
| `identity.invoice_number` | Missing or empty invoice number |
| `identity.sender_name` | Missing vendor/sender name |
| `identity.recipient_name` | Missing recipient/buyer name |
| `items.non_empty` | No line items |
| `arithmetic.line_total` | line_total ≠ qty × unit_price |
| `arithmetic.subtotal` | subtotal ≠ sum of line_totals |
| `arithmetic.total` | total ≠ subtotal + tax_amount |

No AI. No heuristics. Every check is deterministic and objectively verifiable.

## CLI

```
trustrender validate <data.json> [--zugferd] [--format text|json]
trustrender ingest <data.json> [-o canonical.json]
trustrender render <template> <data.json> -o <output.pdf> [--zugferd en16931]
trustrender preflight <template> <data.json> [--zugferd en16931]
trustrender serve --templates <dir> [--port 8190]
trustrender doctor [--smoke]
```

## Integration with factur-x / drafthorse

TrustRender validates and normalizes. You generate and embed with the library of your choice.

```python
from trustrender import validate_invoice

# Step 1: Validate with TrustRender
result = validate_invoice(messy_data, zugferd=True)
if not result["render_ready"] or not result["zugferd_ready"]:
    raise ValueError(f"Invoice blocked: {result['errors']}")

# Step 2: Use the canonical payload with drafthorse or factur-x
canonical = result["canonical"]
# ... your existing ZUGFeRD generation code here
```

## EN 16931 e-invoicing (narrow scope)

Catches many document-level and ZUGFeRD/EN 16931 readiness issues before embedding. Currently supports:

- **Domestic German B2B invoices** with standard VAT, EUR, SEPA payment
- Single or mixed VAT rates (7% + 19%)
- Invoice type 380 and credit note 381
- PDF/A-3b with embedded CII XML (requires `trustrender[render]`)

Not supported (fails loudly): reverse charge, cross-border, allowances/charges, non-EUR currencies.

See [docs/einvoice-scope.md](docs/einvoice-scope.md) for the full scope matrix.

## Optional: PDF rendering

If you also want TrustRender to generate PDFs (not just validate):

```
pip install "trustrender[render]"
trustrender render invoice.j2.typ data.json -o invoice.pdf --zugferd en16931
```

Rendering uses Typst — no browser, no Chromium. Fast and deterministic.

## What this is not

- Not a full AP automation platform
- Not an e-invoice compliance certification
- Not an AI-powered data fixer (all corrections are deterministic)
- Not a replacement for factur-x or drafthorse — it's the validation layer you run before them

## Development

```
pip install -e ".[dev]"
trustrender doctor --smoke
pytest
```

## License

MIT
