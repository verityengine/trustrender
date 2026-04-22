"""Tests for source adapters (Stripe first)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from trustrender import validate_invoice
from trustrender.adapters.shopify import from_shopify
from trustrender.adapters.stripe import from_stripe

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
        result = from_stripe(
            {
                "customer_name": "Acme Corp",
                "customer_email": "billing@acme.com",
            }
        )
        assert result["recipient"]["name"] == "Acme Corp"
        assert result["recipient"]["email"] == "billing@acme.com"

    def test_customer_address_flattened_and_structured(self):
        result = from_stripe(
            {
                "customer_address": {
                    "line1": "123 Main St",
                    "city": "Chicago",
                    "state": "IL",
                    "postal_code": "60601",
                    "country": "US",
                },
            }
        )
        # Flattened string for canonical address field
        addr = result["recipient"]["address"]
        assert "123 Main St" in addr
        assert "Chicago" in addr

        # Structured fields preserved for ZUGFeRD handoff
        assert result["recipient"]["city"] == "Chicago"
        assert result["recipient"]["postal_code"] == "60601"
        assert result["recipient"]["country"] == "US"

    def test_expanded_customer_object(self):
        result = from_stripe(
            {
                "customer": {
                    "name": "Expanded Corp",
                    "email": "expanded@corp.com",
                },
            }
        )
        assert result["recipient"]["name"] == "Expanded Corp"
        assert result["recipient"]["email"] == "expanded@corp.com"

    def test_line_items_extracted(self):
        result = from_stripe(
            {
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
            }
        )
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

    def test_sender_passthrough(self):
        """If user enriches source with sender dict, adapter preserves it."""
        result = from_stripe({"number": "INV-001", "sender": {"name": "Acme GmbH"}})
        assert result["sender"] == {"name": "Acme GmbH"}

    def test_vendor_passthrough_as_sender(self):
        """vendor dict maps to sender if sender absent."""
        result = from_stripe({"number": "INV-001", "vendor": {"name": "Acme GmbH"}})
        assert result["sender"] == {"name": "Acme GmbH"}

    def test_seller_passthrough_as_sender(self):
        """seller dict maps to sender if sender and vendor absent."""
        result = from_stripe({"number": "INV-001", "seller": {"name": "Acme GmbH"}})
        assert result["sender"] == {"name": "Acme GmbH"}

    def test_sender_takes_priority_over_vendor(self):
        """First valid dict wins: sender > vendor > seller."""
        result = from_stripe(
            {
                "number": "INV-001",
                "sender": {"name": "Sender"},
                "vendor": {"name": "Vendor"},
            }
        )
        assert result["sender"]["name"] == "Sender"

    def test_non_dict_sender_ignored(self):
        """String sender is not a valid enrichment — ignored."""
        result = from_stripe({"number": "INV-001", "sender": "Acme GmbH"})
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

    def test_structured_address_survives_validation(self):
        """Structured address fields survive through validate_invoice for ZUGFeRD handoff."""
        raw = json.loads((FIXTURES / "stripe_invoice.json").read_text())
        adapted = from_stripe(raw)
        adapted["sender"] = {"name": "Buildspace Labs Inc."}
        result = validate_invoice(adapted)

        # Canonical recipient.address is a string
        recipient = result["canonical"]["recipient"]
        assert isinstance(recipient["address"], str)
        assert "200 Corporate Plaza" in recipient["address"]

    def test_zugferd_xml_with_stripe_data(self):
        """from_stripe → validate → build_invoice_xml should work with full data."""

        raw = json.loads((FIXTURES / "stripe_invoice.json").read_text())
        adapted = from_stripe(raw)

        # Supply full seller data needed for ZUGFeRD
        adapted["sender"] = {
            "name": "Buildspace Labs Inc.",
            "address": "500 Tech Park Dr",
            "city": "San Francisco",
            "postal_code": "94105",
            "country": "DE",
            "vat_id": "DE123456789",
            "email": "billing@buildspace.so",
        }

        result = validate_invoice(adapted)
        assert result["render_ready"] is True

        # Recipient should have structured fields from adapter
        assert adapted["recipient"]["city"] == "Chicago"
        assert adapted["recipient"]["postal_code"] == "60601"
        assert adapted["recipient"]["country"] == "US"

    def test_amounts_are_dollars_not_cents(self):
        """Verify cents→dollars conversion happened correctly."""
        raw = json.loads((FIXTURES / "stripe_invoice.json").read_text())
        adapted = from_stripe(raw)

        # Raw Stripe: subtotal=59300 (cents) → adapted should be 593.00
        assert adapted["subtotal"] == 593.00
        assert adapted["tax_amount"] == 50.40
        assert adapted["total"] == 643.40


# ── from_shopify: structural transformation ──────────────────────────


class TestShopifyAdapter:
    def test_order_number_from_name(self):
        result = from_shopify({"name": "#1047"})
        assert result["invoice_number"] == "1047"

    def test_order_number_fallback(self):
        result = from_shopify({"order_number": 1047})
        assert result["invoice_number"] == "1047"

    def test_amounts_strings_to_floats(self):
        result = from_shopify(
            {
                "subtotal_price": "100.00",
                "total_tax": "19.00",
                "total_price": "119.00",
            }
        )
        assert result["subtotal"] == 100.00
        assert result["tax_amount"] == 19.00
        assert result["total"] == 119.00

    def test_date_extracted(self):
        result = from_shopify({"created_at": "2026-04-08T14:30:00+02:00"})
        assert result["invoice_date"] == "2026-04-08"

    def test_currency_preserved(self):
        result = from_shopify({"currency": "EUR"})
        assert result["currency"] == "EUR"

    def test_customer_name_combined(self):
        result = from_shopify(
            {
                "customer": {"first_name": "Klaus", "last_name": "Berger"},
            }
        )
        assert result["recipient"]["name"] == "Klaus Berger"

    def test_customer_email(self):
        result = from_shopify(
            {
                "customer": {"first_name": "A", "last_name": "B", "email": "a@b.com"},
            }
        )
        assert result["recipient"]["email"] == "a@b.com"

    def test_billing_address_flattened_and_structured(self):
        result = from_shopify(
            {
                "billing_address": {
                    "address1": "Werkstr. 15",
                    "city": "Düsseldorf",
                    "province": "NRW",
                    "zip": "40210",
                    "country": "Germany",
                    "country_code": "DE",
                },
            }
        )
        assert "Werkstr. 15" in result["recipient"]["address"]
        assert result["recipient"]["city"] == "Düsseldorf"
        assert result["recipient"]["postal_code"] == "40210"
        assert result["recipient"]["country"] == "DE"

    def test_line_items_mapped(self):
        result = from_shopify(
            {
                "line_items": [
                    {"title": "Widget", "quantity": 3, "price": "25.00"},
                ],
            }
        )
        assert len(result["items"]) == 1
        item = result["items"][0]
        assert item["description"] == "Widget"
        assert item["quantity"] == 3
        assert item["unit_price"] == 25.00
        assert item["line_total"] == 75.00

    def test_no_sender_in_output(self):
        result = from_shopify({"name": "#1", "customer": {"first_name": "A", "last_name": "B"}})
        assert "sender" not in result

    def test_sender_passthrough(self):
        result = from_shopify({"name": "#1", "sender": {"name": "Werkzeug GmbH"}})
        assert result["sender"] == {"name": "Werkzeug GmbH"}

    def test_vendor_passthrough_as_sender(self):
        result = from_shopify({"name": "#1", "vendor": {"name": "Werkzeug GmbH"}})
        assert result["sender"] == {"name": "Werkzeug GmbH"}

    def test_non_dict_sender_ignored(self):
        result = from_shopify({"name": "#1", "sender": "Werkzeug GmbH"})
        assert "sender" not in result

    def test_missing_fields_left_missing(self):
        result = from_shopify({})
        assert "invoice_number" not in result
        assert "subtotal" not in result

    def test_tax_rate_from_tax_lines(self):
        result = from_shopify(
            {
                "tax_lines": [{"title": "VAT", "price": "19.00", "rate": 0.19}],
            }
        )
        assert result["tax_rate"] == 0.19

    def test_rejects_non_dict(self):
        with pytest.raises(ValueError):
            from_shopify("not a dict")

    def test_billing_address_name_fallback(self):
        """If customer has no name, use billing_address.name."""
        result = from_shopify(
            {
                "customer": {"email": "test@test.com"},
                "billing_address": {"name": "Klaus Berger"},
            }
        )
        assert result["recipient"]["name"] == "Klaus Berger"


# ── Shopify end-to-end ───────────────────────────────────────────────


class TestShopifyEndToEnd:
    def test_full_fixture_validates(self):
        raw = json.loads((FIXTURES / "shopify_order.json").read_text())
        adapted = from_shopify(raw)
        result = validate_invoice(adapted)

        # Blocks on missing sender
        assert result["status"] == "blocked"
        blocked_rules = {e["rule_id"] for e in result["errors"] if e.get("severity") == "blocked"}
        assert "identity.sender_name" in blocked_rules

        # But data is correct
        canonical = result["canonical"]
        assert canonical["invoice_number"] == "1047"
        assert canonical["recipient"]["name"] == "Klaus Berger"
        assert canonical["total"] == pytest.approx(1309.00)
        assert canonical["currency"] == "EUR"
        assert len(canonical["items"]) == 3

    def test_full_fixture_with_sender_passes(self):
        raw = json.loads((FIXTURES / "shopify_order.json").read_text())
        adapted = from_shopify(raw)
        adapted["sender"] = {"name": "Werkzeug-Shop GmbH", "email": "shop@werkzeug.de"}
        result = validate_invoice(adapted)
        assert result["render_ready"] is True

    def test_incomplete_fixture_blocks(self):
        raw = json.loads((FIXTURES / "shopify_incomplete.json").read_text())
        adapted = from_shopify(raw)
        result = validate_invoice(adapted)
        assert result["status"] == "blocked"
        blocked_rules = {e["rule_id"] for e in result["errors"] if e.get("severity") == "blocked"}
        assert "identity.sender_name" in blocked_rules
        assert "identity.recipient_name" in blocked_rules

    def test_amounts_are_floats_not_strings(self):
        raw = json.loads((FIXTURES / "shopify_order.json").read_text())
        adapted = from_shopify(raw)
        assert isinstance(adapted["subtotal"], float)
        assert adapted["subtotal"] == 1100.00
        assert adapted["total"] == 1309.00
        # First item: 5 × 120.00 = 600.00
        assert adapted["items"][0]["line_total"] == 600.00
        assert adapted["items"][0]["unit_price"] == 120.00
