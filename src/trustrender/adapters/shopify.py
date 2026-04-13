"""Shopify Order adapter.

Converts a raw Shopify Admin API order response
(GET /admin/api/2024-01/orders/{id}.json) into a dict that
ingest_invoice() can normalize and validate.

Shopify has orders, not invoices. This adapter maps order data
to invoice-like structure for validation before e-invoice embedding.

Key transformations:
  - Amounts: decimal strings ("100.00") → floats
  - Dates: ISO 8601 strings → YYYY-MM-DD
  - Customer name: first_name + last_name → combined name string
  - Line items: title → description, price (per-unit string) → unit_price (float)
  - Line totals: computed as quantity × unit_price (Shopify doesn't always include them)
  - Billing address: structured fields preserved for ZUGFeRD handoff
  - Seller: NOT included in Shopify orders. Adapter leaves sender empty.
    The validation pipeline will flag missing sender data — this is correct behavior.

Usage::

    from trustrender import validate_invoice
    from trustrender.adapters import from_shopify

    result = validate_invoice(from_shopify(raw_shopify_order))
"""

from __future__ import annotations


def from_shopify(raw: dict) -> dict:
    """Convert raw Shopify Order API response to ingest-ready dict.

    Args:
        raw: The full JSON response from GET /admin/api/.../orders/{id}.json.
             Amounts are decimal strings. Currency is uppercase.

    Returns:
        A dict ready for ingest_invoice(). Not yet canonical,
        not yet validated — just structurally bridged.

    Raises:
        ValueError: If raw is not a dict.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"from_shopify expects a dict, got {type(raw).__name__}")

    out: dict = {}

    # ── Order identity ───────────────────────────────────────────

    # Shopify uses "name" ("#1001") or "order_number" (1001)
    if "name" in raw:
        out["invoice_number"] = str(raw["name"]).lstrip("#")
    elif "order_number" in raw:
        out["invoice_number"] = str(raw["order_number"])

    if "created_at" in raw and isinstance(raw["created_at"], str):
        out["invoice_date"] = raw["created_at"][:10]  # ISO 8601 → YYYY-MM-DD

    # Shopify orders have no due_date — they are immediate payment

    if "currency" in raw:
        out["currency"] = raw["currency"]

    # ── Amounts (strings → floats) ───────────────────────────────

    for src, dst in [
        ("subtotal_price", "subtotal"),
        ("total_tax", "tax_amount"),
        ("total_price", "total"),
    ]:
        val = raw.get(src)
        if val is not None:
            try:
                out[dst] = float(val)
            except (ValueError, TypeError):
                pass

    # ── Tax rate (from top-level tax_lines if available) ─────────

    tax_lines = raw.get("tax_lines")
    if isinstance(tax_lines, list) and len(tax_lines) == 1:
        rate = tax_lines[0].get("rate")
        if isinstance(rate, (int, float)):
            out["tax_rate"] = rate

    # ── Customer → recipient ─────────────────────────────────────

    recipient: dict = {}

    if isinstance(raw.get("customer"), dict):
        cust = raw["customer"]
        name_parts = []
        if cust.get("first_name"):
            name_parts.append(cust["first_name"])
        if cust.get("last_name"):
            name_parts.append(cust["last_name"])
        if name_parts:
            recipient["name"] = " ".join(name_parts)
        if cust.get("email"):
            recipient["email"] = cust["email"]

    # Billing address
    if isinstance(raw.get("billing_address"), dict):
        addr = raw["billing_address"]
        # Use billing_address.name as fallback for recipient name
        if not recipient.get("name") and addr.get("name"):
            recipient["name"] = addr["name"]
        # Flatten to string for canonical address field
        recipient["address"] = _flatten_address(addr)
        # Preserve structured fields for ZUGFeRD handoff
        if addr.get("city"):
            recipient["city"] = addr["city"]
        if addr.get("zip"):
            recipient["postal_code"] = addr["zip"]
        if addr.get("country_code"):
            recipient["country"] = addr["country_code"]

    if recipient:
        out["recipient"] = recipient

    # Seller is NOT available in Shopify order objects.
    # The validation pipeline will flag this as blocked if sender.name is required.

    # ── Line items ───────────────────────────────────────────────

    if isinstance(raw.get("line_items"), list):
        items = []
        for li in raw["line_items"]:
            if not isinstance(li, dict):
                continue
            item: dict = {}

            if "title" in li:
                item["description"] = li["title"]
            if "quantity" in li:
                item["quantity"] = li["quantity"]

            # Price is per-unit, as a string
            if "price" in li:
                try:
                    unit_price = float(li["price"])
                    item["unit_price"] = unit_price
                    # Compute line_total (Shopify doesn't always include it)
                    if "quantity" in li:
                        item["line_total"] = unit_price * li["quantity"]
                except (ValueError, TypeError):
                    pass

            if item:
                items.append(item)

        if items:
            out["items"] = items

    return out


def _flatten_address(addr: dict) -> str:
    """Flatten Shopify address object into a single string."""
    parts = []
    if addr.get("address1"):
        parts.append(addr["address1"])
    if addr.get("address2"):
        parts.append(addr["address2"])
    city_parts = []
    if addr.get("city"):
        city_parts.append(addr["city"])
    if addr.get("province"):
        city_parts.append(addr["province"])
    if addr.get("zip"):
        city_parts.append(addr["zip"])
    if city_parts:
        parts.append(", ".join(city_parts))
    if addr.get("country"):
        parts.append(addr["country"])
    return ", ".join(parts)
