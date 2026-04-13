"""Stripe Invoice adapter.

Converts a raw Stripe Invoice API response (GET /v1/invoices/:id)
into a dict that ingest_invoice() can normalize and validate.

Key transformations:
  - Amounts: cents (int) → dollars (float), divide by 100
  - Dates: Unix timestamps (int) → YYYY-MM-DD strings
  - Line items: extract from lines.data[], pull unit_amount from nested price object
  - Customer: Stripe's customer is the buyer → maps to recipient
  - Currency: lowercased in Stripe → uppercased for canonical
  - Seller: NOT included in Stripe invoice objects. Adapter leaves sender empty.
    The validation pipeline will flag missing sender data — this is correct behavior,
    not a bug. Users must supply seller identity separately.

Usage::

    from trustrender import validate_invoice
    from trustrender.adapters import from_stripe

    result = validate_invoice(from_stripe(raw_stripe_response))
"""

from __future__ import annotations

from datetime import datetime, timezone


def from_stripe(raw: dict) -> dict:
    """Convert raw Stripe Invoice API response to ingest-ready dict.

    Args:
        raw: The full JSON response from GET /v1/invoices/:id.
             Amounts must be in cents (Stripe's native format).

    Returns:
        A dict ready for ingest_invoice(). Not yet canonical,
        not yet validated — just structurally bridged.

    Raises:
        ValueError: If raw is not a dict.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"from_stripe expects a dict, got {type(raw).__name__}")

    out: dict = {}

    # ── Invoice identity ─────────────────────────────────────────

    if "number" in raw:
        out["invoice_number"] = raw["number"]

    if "created" in raw and isinstance(raw["created"], (int, float)):
        out["invoice_date"] = _unix_to_date(raw["created"])

    if "due_date" in raw and isinstance(raw["due_date"], (int, float)):
        out["due_date"] = _unix_to_date(raw["due_date"])

    if "currency" in raw:
        out["currency"] = raw["currency"].upper()

    # ── Amounts (cents → dollars) ────────────────────────────────

    if "subtotal" in raw and isinstance(raw["subtotal"], (int, float)):
        out["subtotal"] = raw["subtotal"] / 100

    if "tax" in raw and isinstance(raw["tax"], (int, float)):
        out["tax_amount"] = raw["tax"] / 100

    if "total" in raw and isinstance(raw["total"], (int, float)):
        out["total"] = raw["total"] / 100

    # ── Customer → recipient ─────────────────────────────────────
    # Stripe's "customer" is the buyer. Maps to recipient, not sender.

    recipient: dict = {}

    if raw.get("customer_name"):
        recipient["name"] = raw["customer_name"]
    if raw.get("customer_email"):
        recipient["email"] = raw["customer_email"]
    if isinstance(raw.get("customer_address"), dict):
        recipient["address"] = _flatten_address(raw["customer_address"])

    # Expanded customer object (if customer was expanded in the API call)
    if isinstance(raw.get("customer"), dict):
        cust = raw["customer"]
        if not recipient.get("name") and cust.get("name"):
            recipient["name"] = cust["name"]
        if not recipient.get("email") and cust.get("email"):
            recipient["email"] = cust["email"]

    if recipient:
        out["recipient"] = recipient

    # Sender is NOT available in Stripe invoice objects.
    # The validation pipeline will flag this as blocked if sender.name is required.
    # This is intentional — users must supply seller identity separately.

    # ── Line items ───────────────────────────────────────────────

    lines_obj = raw.get("lines")
    if isinstance(lines_obj, dict) and isinstance(lines_obj.get("data"), list):
        items = []
        for line in lines_obj["data"]:
            if not isinstance(line, dict):
                continue
            item: dict = {}

            if "description" in line:
                item["description"] = line["description"]
            if "quantity" in line and line["quantity"] is not None:
                item["quantity"] = line["quantity"]

            # unit_amount lives on the nested price object
            price_obj = line.get("price")
            if isinstance(price_obj, dict):
                ua = price_obj.get("unit_amount")
                if isinstance(ua, (int, float)):
                    item["unit_price"] = ua / 100

            # line-level amount (cents → dollars)
            if "amount" in line and isinstance(line["amount"], (int, float)):
                item["line_total"] = line["amount"] / 100

            if item:
                items.append(item)

        if items:
            out["items"] = items

    # ── Metadata passthrough ─────────────────────────────────────

    if isinstance(raw.get("metadata"), dict) and raw["metadata"]:
        out["_metadata"] = raw["metadata"]

    return out


def _unix_to_date(ts: int | float) -> str:
    """Convert Unix timestamp to YYYY-MM-DD string."""
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d")


def _flatten_address(addr: dict) -> str:
    """Flatten Stripe address object into a single string."""
    parts = []
    if addr.get("line1"):
        parts.append(addr["line1"])
    if addr.get("line2"):
        parts.append(addr["line2"])
    city_state = []
    if addr.get("city"):
        city_state.append(addr["city"])
    if addr.get("state"):
        city_state.append(addr["state"])
    if addr.get("postal_code"):
        city_state.append(addr["postal_code"])
    if city_state:
        parts.append(", ".join(city_state))
    if addr.get("country"):
        parts.append(addr["country"])
    return ", ".join(parts)
