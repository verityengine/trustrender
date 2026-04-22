# TrustRender

[![PyPI](https://img.shields.io/pypi/v/trustrender.svg)](https://pypi.org/project/trustrender/)
[![Python](https://img.shields.io/pypi/pyversions/trustrender.svg)](https://pypi.org/project/trustrender/)
[![Tests](https://img.shields.io/github/actions/workflow/status/verityengine/trustrender/ci.yml?branch=main&label=tests)](https://github.com/verityengine/trustrender/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

Validate and normalize billing data before Factur-X/ZUGFeRD embedding.

## Quick start

```
pip install trustrender
```

Stripe and Shopify billing exports don't include the seller fields required for compliant invoices. TrustRender catches this:

```
$ trustrender validate examples/demo_stripe.json --source stripe

Invoice:   INV-2026-0187
From:
To:        Rheingold Maschinenbau GmbH
Items:     3
Total:     $2,945.25

BLOCKED — 1 problem(s)

  Missing vendor/sender name
    Add a sender.name field to your invoice data.

This invoice cannot be processed until the problems above are fixed.
```

```
$ trustrender validate examples/demo_shopify.json --source shopify

Invoice:   1047
From:
To:        Klaus Berger
Items:     3
Total:     $1,309.00

BLOCKED — 1 problem(s)

  Missing vendor/sender name
    Add a sender.name field to your invoice data.

This invoice cannot be processed until the problems above are fixed.
```

Add your seller identity to the source payload and it passes:

```
$ trustrender validate examples/demo_stripe_ready.json --source stripe

Invoice:   INV-2026-0187
From:      NovaTech Solutions GmbH
To:        Rheingold Maschinenbau GmbH
Items:     3
Total:     $2,945.25

PASS — invoice data is valid

Safe to embed in Factur-X/ZUGFeRD PDF.
```

```
$ trustrender validate examples/demo_shopify_ready.json --source shopify

Invoice:   1047
From:      Werkzeug-Kontor GmbH
To:        Klaus Berger
Items:     3
Total:     $1,309.00

PASS — invoice data is valid

Safe to embed in Factur-X/ZUGFeRD PDF.
```

The only difference between the blocked and passing files is one added field:

```json
"sender": { "name": "NovaTech Solutions GmbH" }
```

## Why this exists

Stripe and Shopify billing exports are missing seller fields, use platform-specific formats (cents, Unix timestamps, decimal strings), and have no concept of tax compliance. [factur-x](https://github.com/akretion/factur-x) and [drafthorse](https://github.com/pretix/python-drafthorse) generate compliant Factur-X/ZUGFeRD XML, but they assume clean input. TrustRender validates and normalizes source billing data before handoff — it catches arithmetic mismatches, missing required fields, and structural problems so they don't silently produce non-compliant documents.

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
from trustrender.adapters import from_stripe

# Raw Stripe API response → canonical invoice (structural validation)
result = validate_invoice(from_stripe(raw_stripe_response))

if result["render_ready"]:
    canonical = result["canonical"]
    # canonical is now ready for either:
    #   - your own template renderer (most users)
    #   - the to_zugferd_data() bridge → drafthorse / factur-x (see end-to-end example below)
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

The `zugferd=True` flag is also accepted but only useful if your input is already in ZUGFeRD shape (with `seller`/`buyer`/`tax_entries`/`payment` keys). For Stripe and Shopify, use the `to_zugferd_data()` bridge after `validate_invoice()` instead — see the end-to-end example below.

Also works with messy data from any source:

```python
result = validate_invoice({
    "invoiceNo": "INV-001",
    "vendor": {"companyName": "Acme Corp"},
    "customer": {"Name": "Client Inc"},
    "LineItems": [{"desc": "Widget", "qty": 2, "unitPrice": 50, "amount": 100}],
    "SubTotal": 100,
    "tax": 8.50,
    "TotalAmt": 108.50,
}, zugferd=True)
```

## Stripe adapter

Raw Stripe Invoice API responses use cents, Unix timestamps, and nested structures. The adapter handles all of it:

```bash
trustrender validate stripe_invoice.json --source stripe --zugferd
```

```python
from trustrender.adapters import from_stripe
result = validate_invoice(from_stripe(raw_stripe_response), zugferd=True)
```

Converts cents to dollars, timestamps to dates, extracts line items from `lines.data[]`, maps customer fields to recipient. If you enrich the source payload with `sender`, `vendor`, or `seller`, the adapter passes it through.

## Shopify adapter

Shopify orders use decimal strings, split customer names, and a different structure from invoices:

```bash
trustrender validate shopify_order.json --source shopify
```

```python
from trustrender.adapters import from_shopify
result = validate_invoice(from_shopify(raw_shopify_order))
```

Parses string amounts to floats, combines first_name + last_name, maps order fields to invoice structure, preserves structured address fields. Shopify orders have no seller info or due date — TrustRender flags the missing seller and handles the absent due date correctly.

## End-to-end example: Stripe → real Factur-X PDF

[`examples/with_drafthorse_facturx.py`](examples/with_drafthorse_facturx.py) runs the full pipeline:

```python
from trustrender import validate_invoice
from trustrender.adapters import from_stripe
from trustrender.zugferd import to_zugferd_data, build_invoice_xml, apply_zugferd

# 1. Adapt + validate the Stripe payload (canonical structure check)
result = validate_invoice(from_stripe(stripe_invoice))

# 2. Bridge canonical → ZUGFeRD shape with the three things Stripe never includes:
#    seller VAT/address, payment IBAN, applicable tax rate
zugferd_data = to_zugferd_data(
    result["canonical"],
    seller={"name": "...", "address": "...", "city": "...",
            "postal_code": "...", "country": "DE", "vat_id": "DE..."},
    payment={"means": "credit_transfer", "iban": "DE..."},
    tax_rate=19,
)
# Real EN 16931 contract validation runs here — catches anything XML build would reject.

# 3. drafthorse builds UN/CEFACT CII XML
xml_bytes = build_invoice_xml(zugferd_data)

# 4. factur-x embeds the XML into a PDF/A-3b container
factur_x_pdf = apply_zugferd(your_visual_pdf_bytes, xml_bytes, lang="de")
```

Output: a 15 KB Factur-X invoice PDF that validates against the EN 16931 XSD ([sample committed at `examples/invoice_facturx.pdf`](examples/invoice_facturx.pdf)).

```
$ python examples/with_drafthorse_facturx.py
Step 1: Adapt + validate via TrustRender (canonical structure)  → status=ready
Step 2: Bridge canonical → ZUGFeRD shape (one call)             → passes EN 16931 contract validation
Step 3: Build CII XML via drafthorse                            → 8,312 bytes of CII XML
Step 4: Render visual PDF (your template)                       → 1,599 bytes
Step 5: Embed CII XML as PDF/A-3b                               → 15,004 bytes
Step 6: Verify with factur-x library                            → ✓ passes EN 16931 XSD
✓ factur-x.xml is embedded in the PDF
```

What's TrustRender vs what's you: the seller VAT, payment IBAN, and tax rate come from your billing setup — Stripe's API doesn't include them, and TrustRender doesn't invent them. Everything else is automatic.

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

## EN 16931 e-invoicing (narrow scope)

Catches structural and contract-level EN 16931 issues before drafthorse builds the XML. Currently supports:

- **Domestic German B2B invoices** with standard VAT, EUR, SEPA payment
- Single VAT rate per invoice (mixed rates not yet supported in the bridge)
- Invoice type 380 and credit note 381
- PDF/A-3b with embedded CII XML via `apply_zugferd()` (wraps `factur-x.attach_xml`)

Not supported, fails loudly: reverse charge, cross-border, allowances/charges, non-EUR currencies, non-DE seller country.

What still slips past TrustRender: things only the official Schematron rules catch (cross-field business rules, value range checks). Run [`xml_check_xsd`](https://github.com/akretion/factur-x) and `xml_check_schematron` on the produced XML for full compliance certainty.

See [docs/einvoice-scope.md](docs/einvoice-scope.md) for the full scope matrix.

## Optional: PDF rendering (legacy)

TrustRender also includes a Jinja2 + Typst PDF render engine — the original product before the validation pivot. It is kept for users who want a single package that does both data validation and PDF rendering, but it is not part of the validation wedge and most users should use their own template engine and just hand TrustRender the data.

```
pip install "trustrender[render]"
trustrender render invoice.j2.typ data.json -o invoice.pdf --zugferd en16931
```

Rendering uses Typst — no browser, no Chromium. Fast and deterministic.

## What this is not

- Not a full AP automation platform
- Not an e-invoice compliance certification (run Schematron on the output XML for that)
- Not an AI-powered data fixer (all corrections are deterministic)
- Not a replacement for factur-x or drafthorse — it's the validation layer you run before them, plus thin wrappers around their entry points
- Not a billing platform replacement — it expects you already collect payment via Stripe / Shopify / something else

## Development

```
pip install -e ".[dev]"
trustrender doctor --smoke
pytest
```

## License

MIT
