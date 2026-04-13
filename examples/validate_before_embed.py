#!/usr/bin/env python3
"""Example: Validate messy invoice data before Factur-X/ZUGFeRD embedding.

TrustRender validates and normalizes. You generate and embed with the
library of your choice (drafthorse, factur-x, or both).

Usage:
    pip install trustrender
    python examples/validate_before_embed.py

No Typst or rendering dependencies required.
"""

from trustrender import validate_invoice


# ── Step 1: Messy invoice data from OCR / ERP / API ──────────────────

messy_invoice = {
    "invoiceNo": "INV-2026-4471",
    "date": "April 10, 2026",
    "dueDate": "May 10, 2026",
    "vendor": {
        "companyName": "Meridian Supply Co.",
        "street": "800 Industrial Pkwy, Munich",
        "mail": "billing@meridian.de",
    },
    "billTo": {
        "Name": "Acme GmbH",
        "address": "100 Hauptstrasse, Berlin",
        "EmailAddress": "ap@acme.de",
    },
    "LineItems": [
        {"desc": "Industrial widget A", "qty": 500, "unitPrice": 24.00, "amount": 12000.00},
        {"desc": "Shipping & handling", "qty": 1, "unitPrice": 450.00, "amount": 450.00},
    ],
    "SubTotal": 12450.00,
    "tax": 2365.50,
    "taxRate": "19%",
    "TotalAmt": 14815.50,
}


# ── Step 2: Validate with TrustRender ────────────────────────────────

result = validate_invoice(messy_invoice)

print(f"Status:         {result['status']}")
print(f"Render ready:   {result['render_ready']}")
print(f"Normalizations: {len(result['normalizations'])}")
print()

if not result["render_ready"]:
    print("BLOCKED — fix these issues before embedding:")
    for error in result["errors"]:
        if error.get("severity") == "blocked":
            print(f"  {error['rule_id']}: {error['message']}")
    exit(1)

# ── Step 3: Use the canonical payload ────────────────────────────────

canonical = result["canonical"]
print(f"Invoice:   {canonical['invoice_number']}")
print(f"From:      {canonical['sender']['name']}")
print(f"To:        {canonical['recipient']['name']}")
print(f"Total:     {canonical['total']}")
print(f"Tax:       {canonical['tax_amount']}")
print(f"Currency:  {canonical['currency']}")
print()

# Show what was normalized
alias_norms = [n for n in result["normalizations"] if n.get("source") == "alias"]
print(f"Field normalizations applied ({len(alias_norms)}):")
for n in alias_norms[:10]:
    print(f"  {n['original_key']} → {n['canonical_name']}")
if len(alias_norms) > 10:
    print(f"  ... and {len(alias_norms) - 10} more")
print()

# ── Step 4: Hand off to drafthorse / factur-x ────────────────────────

print("Canonical payload is ready for ZUGFeRD embedding.")
print("Next steps:")
print("  - Pass canonical to drafthorse.build_invoice_xml()")
print("  - Or pass to factur-x for PDF/A-3 embedding")
print("  - TrustRender already verified the math is correct")

# Example with drafthorse (if installed):
#
#   from drafthorse.models.document import Document
#   doc = Document()
#   doc.header.id = canonical["invoice_number"]
#   doc.header.name = "RECHNUNG"
#   # ... map canonical fields to drafthorse document ...
#   xml_bytes = doc.serialize()
#
# Example with TrustRender's built-in ZUGFeRD (if render extras installed):
#
#   from trustrender import render
#   pdf = render("einvoice.j2.typ", canonical, output="invoice.pdf", zugferd="en16931")
