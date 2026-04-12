"""Tests for structured invoice ingestion pipeline.

10 messy test payloads exercising alias resolution, type coercion,
auto-computation, unknown field classification, and semantic validation.
"""

from __future__ import annotations

import pytest

from trustrender.invoice_ingest import ingest_invoice


# ---------------------------------------------------------------------------
# Test 1: QuickBooks-style camelCase
# ---------------------------------------------------------------------------

class TestQuickBooksCamelCase:
    PAYLOAD = {
        "invoiceNo": "QB-2026-1234",
        "invoiceDate": "April 10, 2026",
        "dueDate": "May 10, 2026",
        "paymentTerms": "Net 30",
        "customer": {
            "companyName": "Contoso Ltd.",
            "street_address": "456 Enterprise Blvd, New York, NY 10001",
            "mail": "accounts@contoso.com",
        },
        "vendor": {
            "business_name": "Acme Corporation",
            "address1": "123 Business Ave, Suite 400, San Francisco, CA 94105",
            "email_address": "billing@acme.com",
        },
        "lineItems": [
            {"desc": "Website redesign", "qty": 1, "unitPrice": "$4,500.00"},
            {"desc": "Logo design", "qty": 1, "unitPrice": "$2,200.00"},
            {"desc": "SEO optimization", "qty": 3, "unitPrice": "$750.00"},
        ],
        "taxRate": "8.5%",
    }

    def test_render_ready(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.render_ready is True
        assert report.status in ("ready", "ready_with_warnings")

    def test_aliases_resolved(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.canonical["invoice_number"] == "QB-2026-1234"
        assert report.canonical["sender"]["name"] == "Acme Corporation"
        assert report.canonical["recipient"]["name"] == "Contoso Ltd."

    def test_dates_normalized(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.canonical["invoice_date"] == "2026-04-10"
        assert report.canonical["due_date"] == "2026-05-10"

    def test_amounts_computed(self):
        report = ingest_invoice(self.PAYLOAD)
        items = report.canonical["items"]
        assert items[0]["line_total"] == 4500.0
        assert items[1]["line_total"] == 2200.0
        assert items[2]["line_total"] == 2250.0
        assert report.canonical["subtotal"] == 8950.0

    def test_tax_computed(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.canonical["tax_rate"] == 8.5
        assert abs(report.canonical["tax_amount"] - 760.75) < 0.01

    def test_normalizations_logged(self):
        report = ingest_invoice(self.PAYLOAD)
        alias_norms = [n for n in report.normalizations if n.source == "alias"]
        assert len(alias_norms) > 0

    def test_template_payload_shape(self):
        report = ingest_invoice(self.PAYLOAD)
        tp = report.template_payload
        assert "sender" in tp
        assert "recipient" in tp
        assert "items" in tp
        assert isinstance(tp["subtotal"], str)  # display format
        assert "$" in tp["subtotal"]


# ---------------------------------------------------------------------------
# Test 2: Stripe-style flat with string amounts
# ---------------------------------------------------------------------------

class TestStripeStyleFlat:
    PAYLOAD = {
        "number": "INV-5678",
        "date": "2026-04-10",
        "due": "2026-05-10",
        "from": {
            "name": "Stripe Seller Inc.",
            "address": "354 Oyster Point Blvd, South San Francisco, CA 94080",
            "email": "invoices@stripe-seller.com",
        },
        "to": {
            "name": "Customer Corp",
            "address": "789 Market St, San Francisco, CA 94103",
            "email": "ap@customer.com",
        },
        "lines": [
            {"title": "API access (monthly)", "count": 1, "price": "$500.00", "amount": "$500.00"},
            {"title": "Premium support", "count": 1, "price": "$200.00", "amount": "$200.00"},
        ],
        "sub_total": "$700.00",
        "tax": "$59.50",
        "taxRate": "8.5%",
        "grand_total": "$759.50",
    }

    def test_render_ready(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.render_ready is True

    def test_aliases_resolved(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.canonical["invoice_number"] == "INV-5678"
        assert report.canonical["sender"]["name"] == "Stripe Seller Inc."
        assert report.canonical["recipient"]["name"] == "Customer Corp"

    def test_amounts_coerced(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.canonical["subtotal"] == 700.0
        assert report.canonical["tax_amount"] == 59.5
        assert report.canonical["total"] == 759.5


# ---------------------------------------------------------------------------
# Test 3: Already canonical — zero normalizations
# ---------------------------------------------------------------------------

class TestAlreadyCanonical:
    PAYLOAD = {
        "invoice_number": "INV-0001",
        "invoice_date": "2026-04-10",
        "due_date": "2026-05-10",
        "sender": {
            "name": "Acme Corp",
            "address": "123 Main St",
            "email": "billing@acme.com",
        },
        "recipient": {
            "name": "Client Inc",
            "address": "456 Oak Ave",
            "email": "ap@client.com",
        },
        "items": [
            {"description": "Consulting", "quantity": 10, "unit_price": 150.0, "line_total": 1500.0, "num": 1},
        ],
        "subtotal": 1500.0,
        "tax_rate": 0,
        "tax_amount": 0,
        "total": 1500.0,
        "currency": "USD",
        "notes": "Thank you for your business.",
    }

    def test_status_ready(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.status == "ready"
        assert report.render_ready is True

    def test_zero_meaningful_normalizations(self):
        report = ingest_invoice(self.PAYLOAD)
        # Only alias/computed/default normalizations count — exact matches filtered out
        assert len(report.normalizations) == 0

    def test_canonical_matches_input(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.canonical["invoice_number"] == "INV-0001"
        assert report.canonical["total"] == 1500.0


# ---------------------------------------------------------------------------
# Test 4: Missing computed fields
# ---------------------------------------------------------------------------

class TestMissingComputedFields:
    PAYLOAD = {
        "invoice_number": "INV-COMP-001",
        "invoice_date": "2026-04-10",
        "due_date": "2026-05-10",
        "sender": {"name": "Builder Co", "address": "100 Oak St"},
        "recipient": {"name": "Client LLC", "address": "200 Pine St"},
        "items": [
            {"description": "Foundation work", "quantity": 1, "unit_price": 5000.0},
            {"description": "Framing", "quantity": 1, "unit_price": 8000.0},
            {"description": "Electrical", "quantity": 1, "unit_price": 3000.0},
        ],
        "tax_rate": 7.5,
    }

    def test_render_ready(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.render_ready is True

    def test_line_totals_computed(self):
        report = ingest_invoice(self.PAYLOAD)
        items = report.canonical["items"]
        assert items[0]["line_total"] == 5000.0
        assert items[1]["line_total"] == 8000.0
        assert items[2]["line_total"] == 3000.0

    def test_subtotal_computed(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.canonical["subtotal"] == 16000.0

    def test_tax_amount_computed(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.canonical["tax_amount"] == 1200.0

    def test_total_computed(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.canonical["total"] == 17200.0

    def test_computed_fields_logged(self):
        report = ingest_invoice(self.PAYLOAD)
        assert "subtotal" in report.computed_fields
        assert "tax_amount" in report.computed_fields
        assert "total" in report.computed_fields


# ---------------------------------------------------------------------------
# Test 5: Near-miss typos — suggestions only, never auto-mapped
# ---------------------------------------------------------------------------

class TestNearMissTypos:
    PAYLOAD = {
        "invioce_number": "INV-TYPO-001",  # typo
        "invoice_date": "2026-04-10",
        "due_date": "2026-05-10",
        "sender": {"name": "Typo Corp", "address": "123 Main St"},
        "recipeint": {"name": "Target LLC", "address": "456 Oak Ave"},  # typo in key
        "items": [
            {"descrption": "Service A", "quantity": 1, "unit_price": 100.0},  # typo
        ],
    }

    def test_blocked_because_invoice_number_not_mapped(self):
        report = ingest_invoice(self.PAYLOAD)
        # invioce_number is a typo — NOT auto-mapped
        assert report.canonical["invoice_number"] == ""
        blocked_rules = [e for e in report.errors if e.severity == "blocked"]
        assert any("invoice_number" in e.message for e in blocked_rules)

    def test_near_match_suggestions(self):
        report = ingest_invoice(self.PAYLOAD)
        near_matches = [u for u in report.unknown_fields if u.classification == "near_match"]
        # invioce_number should be suggested as invoice_number
        suggestions = {u.path: u.suggestion for u in near_matches}
        assert "invioce_number" in suggestions

    def test_never_auto_mapped(self):
        report = ingest_invoice(self.PAYLOAD)
        # The typo'd field should NOT be in the canonical payload
        assert report.canonical["invoice_number"] == ""


# ---------------------------------------------------------------------------
# Test 6: Extra CRM fields — all pass_through
# ---------------------------------------------------------------------------

class TestExtraCRMFields:
    PAYLOAD = {
        "invoice_number": "INV-CRM-001",
        "invoice_date": "2026-04-10",
        "due_date": "2026-05-10",
        "sender": {"name": "CRM Corp", "address": "100 Data St"},
        "recipient": {"name": "Client Inc", "address": "200 Query Ave"},
        "items": [
            {"description": "CRM license", "quantity": 5, "unit_price": 99.0, "line_total": 495.0, "num": 1},
        ],
        "subtotal": 495.0,
        "total": 495.0,
        "salesforce_id": "SF-123456",
        "deal_stage": "Closed Won",
        "account_manager": "Jane Smith",
        "internal_notes": "Upsell opportunity in Q3",
    }

    def test_render_ready(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.render_ready is True

    def test_extra_fields_classified(self):
        report = ingest_invoice(self.PAYLOAD)
        paths = {u.path for u in report.unknown_fields}
        assert "salesforce_id" in paths
        assert "deal_stage" in paths
        assert "account_manager" in paths
        assert "internal_notes" in paths

    def test_extra_fields_are_pass_through(self):
        report = ingest_invoice(self.PAYLOAD)
        for uf in report.unknown_fields:
            if uf.path in ("salesforce_id", "deal_stage", "account_manager", "internal_notes"):
                assert uf.classification == "pass_through"

    def test_extras_preserved(self):
        report = ingest_invoice(self.PAYLOAD)
        extras = report.canonical["extras"]
        assert "salesforce_id" in extras


# ---------------------------------------------------------------------------
# Test 7: Minimal flat API
# ---------------------------------------------------------------------------

class TestMinimalFlatAPI:
    PAYLOAD = {
        "number": "API-001",
        "date": "2026-04-10",
        "due": "2026-05-10",
        "vendor": {"name": "API Vendor", "address": "1 Cloud Way"},
        "client": {"name": "App User", "address": "2 Mobile St"},
        "products": [
            {"name": "API calls (1M)", "qty": 1, "price": 299.0},
            {"name": "Storage (100GB)", "qty": 1, "price": 49.0},
        ],
    }

    def test_render_ready(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.render_ready is True

    def test_aliases_resolved(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.canonical["invoice_number"] == "API-001"
        assert report.canonical["sender"]["name"] == "API Vendor"
        assert report.canonical["recipient"]["name"] == "App User"

    def test_totals_computed(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.canonical["subtotal"] == 348.0
        assert report.canonical["total"] == 348.0

    def test_item_descriptions_from_name(self):
        report = ingest_invoice(self.PAYLOAD)
        items = report.canonical["items"]
        assert items[0]["description"] == "API calls (1M)"
        assert items[1]["description"] == "Storage (100GB)"


# ---------------------------------------------------------------------------
# Test 8: Blocked — missing critical data
# ---------------------------------------------------------------------------

class TestBlockedMissingCritical:
    PAYLOAD = {
        "items": [
            {"description": "Mystery service", "quantity": 1, "unit_price": 500.0},
        ],
    }

    def test_blocked(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.status == "blocked"
        assert report.render_ready is False

    def test_template_payload_is_none(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.template_payload is None

    def test_invoice_number_blocked(self):
        report = ingest_invoice(self.PAYLOAD)
        blocked = [e for e in report.errors if e.severity == "blocked"]
        assert any("invoice_number" in e.message for e in blocked)

    def test_sender_blocked(self):
        report = ingest_invoice(self.PAYLOAD)
        sender_blocked = [e for e in report.errors if "sender" in e.path and e.severity == "blocked"]
        assert len(sender_blocked) > 0

    def test_recipient_blocked(self):
        report = ingest_invoice(self.PAYLOAD)
        recipient_blocked = [e for e in report.errors if "recipient" in e.path and e.severity == "blocked"]
        assert len(recipient_blocked) > 0


# ---------------------------------------------------------------------------
# Test 9: European formats
# ---------------------------------------------------------------------------

class TestEuropeanFormats:
    PAYLOAD = {
        "invoice_number": "RE-2026-001",
        "invoice_date": "10.04.2026",
        "due_date": "10.05.2026",
        "currency": "EUR",
        "sender": {"name": "Muster GmbH", "address": "Musterstraße 1, Berlin"},
        "recipient": {"name": "Kunde AG", "address": "Kundenweg 42, München"},
        "items": [
            {"description": "Beratung", "quantity": 10, "unit_price": "€1.250,00"},
            {"description": "Entwicklung", "quantity": 1, "unit_price": "€3.500,00"},
        ],
        "tax_rate": "19%",
    }

    def test_render_ready(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.render_ready is True

    def test_dates_normalized(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.canonical["invoice_date"] == "2026-04-10"
        assert report.canonical["due_date"] == "2026-05-10"

    def test_european_amounts_parsed(self):
        report = ingest_invoice(self.PAYLOAD)
        items = report.canonical["items"]
        assert items[0]["unit_price"] == 1250.0
        assert items[1]["unit_price"] == 3500.0

    def test_line_totals_computed(self):
        report = ingest_invoice(self.PAYLOAD)
        items = report.canonical["items"]
        assert items[0]["line_total"] == 12500.0
        assert items[1]["line_total"] == 3500.0

    def test_currency_preserved(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.canonical["currency"] == "EUR"

    def test_template_payload_uses_eur(self):
        report = ingest_invoice(self.PAYLOAD)
        tp = report.template_payload
        assert "€" in tp["subtotal"]


# ---------------------------------------------------------------------------
# Test 10: Conflicting arithmetic — error, no override
# ---------------------------------------------------------------------------

class TestConflictingArithmetic:
    PAYLOAD = {
        "invoice_number": "INV-CONFLICT-001",
        "invoice_date": "2026-04-10",
        "due_date": "2026-05-10",
        "sender": {"name": "Math Corp", "address": "1 Calc Ave"},
        "recipient": {"name": "Off By One LLC", "address": "2 Rounding Rd"},
        "items": [
            {"description": "Service A", "quantity": 2, "unit_price": 100.0, "line_total": 200.0, "num": 1},
            {"description": "Service B", "quantity": 3, "unit_price": 50.0, "line_total": 150.0, "num": 2},
        ],
        "subtotal": 999.99,  # WRONG — should be 350.0
        "total": 999.99,
    }

    def test_blocked_due_to_arithmetic_contradiction(self):
        report = ingest_invoice(self.PAYLOAD)
        # A known arithmetic contradiction must block render — the document is not trustworthy
        assert report.render_ready is False
        assert report.status == "blocked"

    def test_template_payload_is_none_when_blocked(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.template_payload is None

    def test_subtotal_not_overridden(self):
        report = ingest_invoice(self.PAYLOAD)
        # The explicitly provided wrong subtotal is preserved — we never override
        assert report.canonical["subtotal"] == 999.99

    def test_arithmetic_blocked_error_reported(self):
        report = ingest_invoice(self.PAYLOAD)
        blocked = [e for e in report.errors if e.severity == "blocked" and "arithmetic" in e.rule_id]
        assert len(blocked) > 0
        subtotal_error = [e for e in blocked if e.path == "subtotal"]
        assert len(subtotal_error) > 0
        assert subtotal_error[0].expected == "350.0"
        assert subtotal_error[0].actual == "999.99"

    def test_total_not_overridden(self):
        report = ingest_invoice(self.PAYLOAD)
        assert report.canonical["total"] == 999.99


# ---------------------------------------------------------------------------
# Integration: Report serialization
# ---------------------------------------------------------------------------

class TestReportSerialization:
    def test_to_dict_shape(self):
        report = ingest_invoice({
            "invoice_number": "SER-001",
            "invoice_date": "2026-04-10",
            "due_date": "2026-05-10",
            "sender": {"name": "A", "address": "1"},
            "recipient": {"name": "B", "address": "2"},
            "items": [{"description": "X", "quantity": 1, "unit_price": 100, "line_total": 100, "num": 1}],
            "subtotal": 100, "total": 100,
        })
        d = report.to_dict()
        assert "status" in d
        assert "render_ready" in d
        assert "canonical" in d
        assert "template_payload" in d
        assert "errors" in d
        assert "warnings" in d
        assert "normalizations" in d
        assert "computed_fields" in d
        assert "unknown_fields" in d

    def test_non_dict_input(self):
        report = ingest_invoice("not a dict")
        assert report.status == "blocked"
        assert report.render_ready is False
        assert report.template_payload is None


# ---------------------------------------------------------------------------
# Integration: Template payload produces renderable shape
# ---------------------------------------------------------------------------

class TestTemplatePayloadShape:
    """Verify template_payload matches what invoice.j2.typ expects."""

    def test_has_required_keys(self):
        report = ingest_invoice({
            "invoice_number": "TPL-001",
            "invoice_date": "2026-04-10",
            "due_date": "2026-05-10",
            "sender": {"name": "A Corp", "address": "1 St", "email": "a@a.com"},
            "recipient": {"name": "B Corp", "address": "2 Ave", "email": "b@b.com"},
            "items": [{"description": "Work", "quantity": 2, "unit_price": 500.0}],
            "tax_rate": 8.5,
        })
        tp = report.template_payload
        # All keys expected by invoice.j2.typ
        for key in ("invoice_number", "invoice_date", "due_date", "sender",
                     "recipient", "items", "subtotal", "tax_rate", "tax_amount", "total"):
            assert key in tp, f"Missing key: {key}"

    def test_item_shape(self):
        report = ingest_invoice({
            "invoice_number": "TPL-002",
            "invoice_date": "2026-04-10",
            "due_date": "2026-05-10",
            "sender": {"name": "A", "address": "1"},
            "recipient": {"name": "B", "address": "2"},
            "items": [{"description": "Svc", "quantity": 3, "unit_price": 100.0}],
        })
        item = report.template_payload["items"][0]
        assert "num" in item
        assert "description" in item
        assert "qty" in item
        assert "unit_price" in item
        assert "amount" in item

    def test_amounts_are_display_strings(self):
        report = ingest_invoice({
            "invoice_number": "TPL-003",
            "invoice_date": "2026-04-10",
            "due_date": "2026-05-10",
            "sender": {"name": "A", "address": "1"},
            "recipient": {"name": "B", "address": "2"},
            "items": [{"description": "X", "quantity": 1, "unit_price": 1234.56}],
        })
        tp = report.template_payload
        assert "$1,234.56" in tp["subtotal"]
        assert "$1,234.56" in tp["total"]

    def test_dates_are_display_format(self):
        report = ingest_invoice({
            "invoice_number": "TPL-004",
            "invoice_date": "2026-04-10",
            "due_date": "2026-05-10",
            "sender": {"name": "A", "address": "1"},
            "recipient": {"name": "B", "address": "2"},
            "items": [{"description": "X", "quantity": 1, "unit_price": 100.0}],
        })
        tp = report.template_payload
        assert tp["invoice_date"] == "April 10, 2026"
        assert tp["due_date"] == "May 10, 2026"
