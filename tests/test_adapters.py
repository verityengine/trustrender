"""Tests for source adapters (Stripe first)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from trustrender.adapters.stripe import from_stripe
from trustrender import validate_invoice

FIXTURES = Path(__file__).parent / "fixtures" / "adapters"


# ── from_stripe: structural transformation ───────────────────────────

class TestStripeAdapter:

    def test_invoice_number(self):
        result = from_stripe({"number": "INV-001"})
        assert result["invoice_number"] == "INV-001"

    def test_amounts_cents_to_dollars(self):
        result = from_stripe({"subtotal": 10000, "tax": 850, "total": 10850})
        assert result["subtotal"] == 100.00
        assert result["tax_amount"] == 8.50
        assert result["total"] == 108.50

    def test_unix_timestamps_to_dates(self):
        result = from_stripe({"created": 1775779200, "due_date": 1778371200})
        assert result["invoice_date"] == "2026-04-10"
        assert result["due_date"] == "2026-05-10"

    def test_currency_uppercased(self):
        result = from_stripe({"currency": "usd"})
        assert result["currency"] == "USD"

    def test_customer_name_and_email(self):
        result = from_stripe({
            "customer_name": "Acme Corp",
            "customer_email": "billing@acme.com",
        })
        assert result["recipient"]["name"] == "Acme Corp"
        assert result["recipient"]["email"] == "billing@acme.com"

    def test_customer_address_flattened(self):
        result = from_stripe({
            "customer_address": {
                "line1": "123 Main St",
                "city": "Chicago",
                "state": "IL",
                "postal_code": "60601",
                "country": "US",
            },
        })
        addr = result["recipient"]["address"]
        assert "123 Main St" in addr
        assert "Chicago" in addr
        assert "IL" in addr

    def test_expanded_customer_object(self):
        result = from_stripe({
            "customer": {
                "name": "Expanded Corp",
                "email": "expanded@corp.com",
            },
        })
        assert result["recipient"]["name"] == "Expanded Corp"
        assert result["recipient"]["email"] == "expanded@corp.com"

    def test_line_items_extracted(self):
        result = from_stripe({
            "lines": {
                "data": [
                    {
                        "description": "Widget",
                        "quantity": 2,
                        "amount": 5000,
                        "price": {"unit_amount": 2500},
                    },
                ],
            },
        })
        assert len(result["items"]) == 1
        item = result["items"][0]
        assert item["description"] == "Widget"
        assert item["quantity"] == 2
        assert item["unit_price"] == 25.00
        assert item["line_total"] == 50.00

    def test_no_sender_in_output(self):
        """Stripe invoices don't include seller info. Adapter must not invent it."""
        result = from_stripe({"number": "INV-001", "customer_name": "Buyer"})
        assert "sender" not in result

    def test_missing_fields_left_missing(self):
        """Adapter does not guess. Missing data stays missing."""
        result = from_stripe({})
        assert "invoice_number" not in result
        assert "subtotal" not in result
        assert "items" not in result

    def test_metadata_passthrough(self):
        result = from_stripe({"metadata": {"po_number": "PO-123"}})
        assert result["_metadata"]["po_number"] == "PO-123"

    def test_rejects_non_dict(self):
        with pytest.raises(ValueError):
            from_stripe("not a dict")
        with pytest.raises(ValueError):
            from_stripe([1, 2, 3])


# ── Full fixture: end-to-end ─────────────────────────────────────────

class TestStripeEndToEnd:

    def test_full_fixture_validates(self):
        """Full Stripe invoice fixture → adapter → validate → pass (except missing sender)."""
        raw = json.loads((FIXTURES / "stripe_invoice.json").read_text())
        adapted = from_stripe(raw)
        result = validate_invoice(adapted)

        # Should block on missing sender (Stripe doesn't include seller)
        assert result["status"] == "blocked"
        blocked_rules = {e["rule_id"] for e in result["errors"] if e.get("severity") == "blocked"}
        assert "identity.sender_name" in blocked_rules

        # But everything else should be correct
        canonical = result["canonical"]
        assert canonical["invoice_number"] == "INV-2026-0042"
        assert canonical["recipient"]["name"] == "Momentum Ventures LLC"
        assert canonical["total"] == pytest.approx(643.40)
        assert canonical["currency"] == "USD"
        assert len(canonical["items"]) == 3

    def test_full_fixture_with_sender_passes(self):
        """Add sender to Stripe output → should pass validation."""
        raw = json.loads((FIXTURES / "stripe_invoice.json").read_text())
        adapted = from_stripe(raw)
        adapted["sender"] = {"name": "Buildspace Labs Inc.", "email": "billing@buildspace.so"}
        result = validate_invoice(adapted)
        assert result["render_ready"] is True

    def test_incomplete_fixture_blocks(self):
        """Stripe invoice missing customer + number → blocks on multiple rules."""
        raw = json.loads((FIXTURES / "stripe_incomplete.json").read_text())
        adapted = from_stripe(raw)
        result = validate_invoice(adapted)
        assert result["status"] == "blocked"
        blocked_rules = {e["rule_id"] for e in result["errors"] if e.get("severity") == "blocked"}
        assert "identity.sender_name" in blocked_rules
        assert "identity.recipient_name" in blocked_rules
        assert "identity.invoice_number" in blocked_rules

    def test_amounts_are_dollars_not_cents(self):
        """Verify cents→dollars conversion happened correctly."""
        raw = json.loads((FIXTURES / "stripe_invoice.json").read_text())
        adapted = from_stripe(raw)

        # Raw Stripe: subtotal=59300 (cents) → adapted should be 593.00
        assert adapted["subtotal"] == 593.00
        assert adapted["tax_amount"] == 50.40
        assert adapted["total"] == 643.40

        # Line items also converted
        assert adapted["items"][0]["line_total"] == 399.00
        assert adapted["items"][0]["unit_price"] == 399.00
        assert adapted["items"][1]["line_total"] == 45.00
