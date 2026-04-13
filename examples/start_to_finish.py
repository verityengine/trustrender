"""
TrustRender: start to finish.

Raw Stripe invoice → validate → blocked → fix → pass → ready for Factur-X.
"""

import json
from trustrender import validate_invoice
from trustrender.adapters import from_stripe

# ── Step 1: Raw Stripe API response (what you actually get back) ─────

stripe_invoice = {
    "number": "INV-2026-0187",
    "currency": "eur",
    "created": 1775779200,
    "due_date": 1778371200,
    "subtotal": 247500,
    "tax": 47025,
    "total": 294525,
    "customer_name": "Rheingold Maschinenbau GmbH",
    "customer_email": "einkauf@rheingold-maschinenbau.de",
    "customer_address": {
        "line1": "Industriestr. 42",
        "city": "Stuttgart",
        "postal_code": "70173",
        "country": "DE",
    },
    "lines": {
        "data": [
            {
                "description": "Cloud infrastructure (Q2 2026)",
                "quantity": 1,
                "amount": 189000,
                "price": {"unit_amount": 189000},
            },
            {
                "description": "Premium support plan",
                "quantity": 1,
                "amount": 45000,
                "price": {"unit_amount": 45000},
            },
            {
                "description": "Data egress overage (2.1 TB)",
                "quantity": 1,
                "amount": 13500,
                "price": {"unit_amount": 13500},
            },
        ],
    },
}

print("=" * 60)
print("Step 1: Raw Stripe invoice")
print("=" * 60)
print(f"  Amounts in cents: subtotal={stripe_invoice['subtotal']}, total={stripe_invoice['total']}")
print(f"  Dates as Unix timestamps: created={stripe_invoice['created']}")
print(f"  No seller info anywhere in the payload")
print()

# ── Step 2: Adapt and validate ───────────────────────────────────────

adapted = from_stripe(stripe_invoice)

print("=" * 60)
print("Step 2: After Stripe adapter")
print("=" * 60)
print(f"  Amounts in euros: subtotal={adapted['subtotal']:.2f}, total={adapted['total']:.2f}")
print(f"  Dates as strings: {adapted['invoice_date']}")
print(f"  Sender: {'(missing)' if 'sender' not in adapted else adapted['sender']}")
print()

result = validate_invoice(adapted)

print("=" * 60)
print("Step 3: Validation result — BLOCKED")
print("=" * 60)
print(f"  Status: {result['status']}")
print(f"  Render ready: {result['render_ready']}")
for error in result["errors"]:
    print(f"  ✗ {error['message']}")
print()

# ── Step 4: Add seller identity and re-validate ─────────────────────

stripe_invoice["sender"] = {"name": "NovaTech Solutions GmbH"}

adapted = from_stripe(stripe_invoice)
adapted["tax_rate"] = 19  # Your tax rate — Stripe doesn't include this
result = validate_invoice(adapted)

print("=" * 60)
print("Step 4: Add sender, re-validate — PASS")
print("=" * 60)
print(f"  Status: {result['status']}")
print(f"  Render ready: {result['render_ready']}")
print()

# ── Step 5: Use the canonical output ─────────────────────────────────

canonical = result["canonical"]

print("=" * 60)
print("Step 5: Canonical invoice (ready for factur-x / drafthorse)")
print("=" * 60)
print(json.dumps(canonical, indent=2, default=str))
