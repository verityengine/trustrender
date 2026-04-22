"""Field alias maps for invoice ingestion.

Maps messy real-world field names to canonical invoice schema names.
Three scoped maps: top-level, party sub-fields, item sub-fields.

Near-match detection uses difflib for suggestions — never auto-maps typos.
"""

from __future__ import annotations

import difflib

# ---------------------------------------------------------------------------
# Alias maps: messy_name -> canonical_name
# ---------------------------------------------------------------------------

# Top-level field aliases
TOP_LEVEL_ALIASES: dict[str, str] = {
    # invoice_number
    "invoiceNo": "invoice_number",
    "invoiceNumber": "invoice_number",
    "InvoiceNumber": "invoice_number",
    "inv_number": "invoice_number",
    "inv_no": "invoice_number",
    "invoice_no": "invoice_number",
    "number": "invoice_number",
    "ref": "invoice_number",
    "reference": "invoice_number",
    "InvoiceRef": "invoice_number",  # ERP/generic PascalCase
    "invoice_ref": "invoice_number",
    "doc_number": "invoice_number",
    "DocNumber": "invoice_number",  # QuickBooks
    # invoice_date
    "invoiceDate": "invoice_date",
    "date": "invoice_date",
    "issued": "invoice_date",
    "issue_date": "invoice_date",
    "TxnDate": "invoice_date",  # QuickBooks
    # due_date
    "dueDate": "due_date",
    "DueDate": "due_date",  # QuickBooks / common PascalCase
    "payment_due": "due_date",
    "due": "due_date",
    "due_by": "due_date",
    # sender
    "seller": "sender",
    "from": "sender",
    "vendor": "sender",
    "supplier": "sender",
    "company": "sender",
    "biller": "sender",
    "issuer": "sender",
    "business": "sender",  # Freshbooks
    # recipient
    "buyer": "recipient",
    "to": "recipient",
    "customer": "recipient",
    "client": "recipient",
    "bill_to": "recipient",
    "billTo": "recipient",
    "Contact": "recipient",  # Xero
    # items
    "line_items": "items",
    "lineItems": "items",
    "LineItems": "items",  # Xero
    "lines": "items",
    "Line": "items",  # QuickBooks
    "products": "items",
    "services": "items",
    "entries": "items",
    # subtotal
    "sub_total": "subtotal",
    "subTotal": "subtotal",
    "SubTotal": "subtotal",  # Xero / QuickBooks
    "net_total": "subtotal",
    "net_amount": "subtotal",
    # tax_rate
    "taxRate": "tax_rate",
    "tax_percent": "tax_rate",
    "vat_rate": "tax_rate",
    # tax_amount
    "taxAmount": "tax_amount",
    "tax": "tax_amount",
    "vat_amount": "tax_amount",
    "vat": "tax_amount",
    "TotalTax": "tax_amount",  # Xero
    # total
    "grand_total": "total",
    "grandTotal": "total",
    "total_amount": "total",
    "totalAmount": "total",
    "amount_due": "total",
    "balance_due": "total",
    "TotalAmt": "total",  # QuickBooks
    "Total": "total",  # Xero
    "total_due": "total",  # CSV exports
    # payment_terms
    "paymentTerms": "payment_terms",
    "terms": "payment_terms",
    # notes
    "memo": "notes",
    "remarks": "notes",
    "comments": "notes",
    "footer": "notes",
    "CustomerMemo": "notes",  # QuickBooks
    # currency
    "currency_code": "currency",
    "currencyCode": "currency",
    "CurrencyCode": "currency",  # Xero
}

# Flat party fields: top-level keys that describe sender/recipient without nesting.
# These are extracted into party objects during pre-processing (Stage 0).
# Format: {flat_key: (party, canonical_sub_field)}
FLAT_SENDER_FIELDS: dict[str, str] = {
    "bill_from_name": "name",
    "bill_from_address": "address",
    "bill_from_email": "email",
    "account_name": "name",  # Stripe
    "account_email": "email",
    "CompanyName": "name",  # QuickBooks
    "CompanyEmail": "email",  # QuickBooks
}

FLAT_RECIPIENT_FIELDS: dict[str, str] = {
    "bill_to_name": "name",
    "bill_to_address": "address",
    "bill_to_email": "email",
    "customer_name": "name",  # Stripe
    "customer_email": "email",  # Stripe
}

# Party (sender/recipient) sub-field aliases
PARTY_ALIASES: dict[str, str] = {
    "company_name": "name",
    "companyName": "name",
    "business_name": "name",
    "organization": "name",
    "Name": "name",  # Xero Contact.Name / PascalCase
    "street": "address",
    "address_line": "address",
    "address1": "address",
    "street_address": "address",
    "email_address": "email",
    "EmailAddress": "email",  # Xero Contact.EmailAddress
    "mail": "email",
}

# Line item sub-field aliases
ITEM_ALIASES: dict[str, str] = {
    "desc": "description",
    "Description": "description",  # Xero / QuickBooks PascalCase
    "name": "description",
    "title": "description",
    "product": "description",
    "service": "description",
    "qty": "quantity",
    "Quantity": "quantity",  # Xero / QuickBooks PascalCase
    "count": "quantity",
    "units": "quantity",
    "price": "unit_price",
    "rate": "unit_price",
    "cost": "unit_price",
    "unit_cost": "unit_price",
    "unitCost": "unit_price",
    "unitPrice": "unit_price",
    "UnitPrice": "unit_price",  # PascalCase variant
    "price_per_unit": "unit_price",
    "total": "line_total",
    "lineTotal": "line_total",
    "line_amount": "line_total",
    "ext_price": "line_total",
    "amount": "line_total",
    "Amount": "line_total",  # QuickBooks / PascalCase
    "taxRate": "tax_rate",
    "vat": "tax_rate",
    "vat_rate": "tax_rate",
    "line_number": "num",
    "LineNum": "num",  # QuickBooks
    "position": "num",
    "pos": "num",
    "index": "num",
    "UnitAmount": "unit_price",  # Xero
    "LineAmount": "line_total",  # Xero
    "unit_amount": "unit_price",  # Stripe (in cents — handled in coercion)
}

# All canonical field names (for near-match detection)
CANONICAL_TOP_LEVEL = {
    "invoice_number",
    "invoice_date",
    "due_date",
    "sender",
    "recipient",
    "items",
    "subtotal",
    "tax_rate",
    "tax_amount",
    "total",
    "currency",
    "payment_terms",
    "notes",
}

CANONICAL_PARTY = {"name", "address", "email"}

CANONICAL_ITEM = {"description", "quantity", "unit_price", "line_total", "num", "tax_rate"}

# Suspicious field name fragments — might be important business fields
_SUSPICIOUS_FRAGMENTS = frozenset(
    {
        "total",
        "amount",
        "price",
        "tax",
        "vat",
        "balance",
        "due",
        "pay",
        "discount",
        "fee",
        "charge",
    }
)


# ---------------------------------------------------------------------------
# Resolution functions
# ---------------------------------------------------------------------------


def resolve_top_level(key: str) -> str | None:
    """Resolve a top-level field name to its canonical name.

    Returns the canonical name if the key is an alias, or None if not recognized.
    Does NOT return the key itself if it's already canonical — caller checks that.
    """
    return TOP_LEVEL_ALIASES.get(key)


def resolve_party_field(key: str) -> str | None:
    """Resolve a party sub-field name to its canonical name."""
    return PARTY_ALIASES.get(key)


def resolve_item_field(key: str) -> str | None:
    """Resolve an item sub-field name to its canonical name."""
    return ITEM_ALIASES.get(key)


def find_near_match(key: str, candidates: set[str]) -> tuple[str, int] | None:
    """Find the closest canonical name for an unknown key.

    Uses difflib with cutoff 0.8 — only returns strong matches.
    Returns (suggested_name, edit_distance) or None.
    Never auto-maps: this is for suggestions only.
    """
    # Also check against alias keys for better coverage
    all_names = candidates | set(TOP_LEVEL_ALIASES.keys())
    matches = difflib.get_close_matches(key, all_names, n=1, cutoff=0.8)
    if not matches:
        return None
    match = matches[0]
    # If match is an alias, resolve to canonical
    canonical = TOP_LEVEL_ALIASES.get(match, match)
    # Compute edit distance for reporting
    distance = _edit_distance(key, match)
    return (canonical, distance)


def classify_unknown(key: str) -> str:
    """Classify an unknown field as 'suspicious' or 'pass_through'.

    Does NOT check near-match — caller does that separately.
    """
    lower = key.lower()
    for fragment in _SUSPICIOUS_FRAGMENTS:
        if fragment in lower:
            return "suspicious"
    return "pass_through"


def _edit_distance(a: str, b: str) -> int:
    """Simple Levenshtein distance."""
    if len(a) < len(b):
        return _edit_distance(b, a)
    if len(b) == 0:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            cost = 0 if ca == cb else 1
            curr.append(min(curr[j] + 1, prev[j + 1] + 1, prev[j] + cost))
        prev = curr
    return prev[len(b)]
