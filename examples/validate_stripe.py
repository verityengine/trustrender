#!/usr/bin/env python3
"""Example: Validate a Stripe Invoice before Factur-X/ZUGFeRD embedding.

Stripe invoice amounts are in cents, dates are Unix timestamps,
and seller info is not included. The adapter handles all of this.

Usage:
    pip install trustrender
    python examples/validate_stripe.py
"""

from trustrender import validate_invoice
from trustrender.adapters import from_stripe


# Raw Stripe Invoice API response (amounts in cents, dates as timestamps)
stripe_response = {
    "number": "INV-2026-0099",
    "currency": "usd",
    "created": 1775779200,         # 2026-04-10
    "due_date": 1778371200,        # 2026-05-10
    "subtotal": 59300,             # $593.00
    "tax": 5040,                   # $50.40
    "total": 64340,                # $643.40
    "customer_name": "Acme GmbH",
    "customer_email": "ap@acme.de",
    "customer_address": {
        "line1": "100 Hauptstrasse",
        "city": "Berlin",
        "country": "DE",
    },
    "lines": {
        "data": [
            {
                "description": "Pro Plan (monthly)",
                "quantity": 1,
                "amount": 39900,
                "price": {"unit_amount": 39900},
            },
            {
                "description": "API overage",
                "quantity": 1,
                "amount": 4500,
                "price": {"unit_amount": 4500},
            },
            {
                "description": "Priority support",
                "quantity": 1,
                "amount": 14900,
                "price": {"unit_amount": 14900},
            },
        ],
    },
}


# Step 1: Adapt (cents → dollars, timestamps → dates, structure → flat)
adapted = from_stripe(stripe_response)

# Step 2: Validate
result = validate_invoice(adapted)

print(f"Status: {result['status']}")
print(f"Invoice: {result['canonical']['invoice_number']}")
print(f"Total: ${result['canonical']['total']:,.2f}")
print(f"Normalizations: {len(result['normalizations'])}")
print()

if not result["render_ready"]:
    print("Blocked:")
    for error in result["errors"]:
        if error.get("severity") == "blocked":
            print(f"  {error['rule_id']}: {error['message']}")
    print()
    print("Note: Stripe invoices don't include seller identity.")
    print("Add sender info to pass validation:")
    print()
    print("  adapted['sender'] = {'name': 'Your Company', 'email': 'billing@you.com'}")
    print("  result = validate_invoice(adapted)")
else:
    print("Ready for Factur-X/ZUGFeRD embedding.")
