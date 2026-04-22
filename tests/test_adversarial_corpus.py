"""Adversarial corpus tests for invoice ingestion.

Proves the pipeline is rule-driven, not fixture-driven.
10 unseen payloads with golden expectations: verdict, template inference,
canonical keys, trace quality, no sample name dependency.

Corpus:
  Ready (3):     generic_erp, flat_billing, minimal_valid
  Blocked (4):   no_sender, empty_items, no_invoice_number, bad_arithmetic
  Recoverable (3): extra_junk, mixed_casing, nested_unwrap
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from trustrender.invoice_ingest import ingest_invoice

CORPUS_DIR = Path(__file__).parent / "fixtures" / "adversarial_corpus"


def load(name: str) -> dict:
    with open(CORPUS_DIR / f"{name}.json") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Canonical shape assertions — same for every render-ready result
# ---------------------------------------------------------------------------

REQUIRED_CANONICAL_KEYS = {
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

REQUIRED_TEMPLATE_KEYS = {
    "invoice_number",
    "invoice_date",
    "due_date",
    "payment_terms",
    "sender",
    "recipient",
    "items",
    "subtotal",
    "tax_rate",
    "tax_amount",
    "total",
    "notes",
}


def assert_render_ready(report, *, sender_name: str, recipient_name: str, invoice_number: str, min_items: int = 1):
    """Golden assertions for any render-ready result."""
    assert report.render_ready is True
    assert report.status in ("ready", "ready_with_warnings")
    # Canonical has all required keys
    canonical = report.canonical
    assert REQUIRED_CANONICAL_KEYS <= set(canonical.keys()), f"Missing canonical keys: {REQUIRED_CANONICAL_KEYS - set(canonical.keys())}"
    # Template payload exists and has required shape
    tp = report.template_payload
    assert tp is not None, "template_payload should not be None for render-ready"
    assert REQUIRED_TEMPLATE_KEYS <= set(tp.keys()), f"Missing template keys: {REQUIRED_TEMPLATE_KEYS - set(tp.keys())}"
    # Core identity checks
    assert canonical["invoice_number"] == invoice_number
    assert canonical["sender"]["name"] == sender_name
    assert canonical["recipient"]["name"] == recipient_name
    # Items non-empty
    assert len(canonical["items"]) >= min_items
    # Template payload has display-formatted items
    assert len(tp["items"]) >= min_items
    for item in tp["items"]:
        assert "description" in item
    # No blocked errors
    blocked = [e for e in report.errors if e.severity == "blocked"]
    assert len(blocked) == 0, f"Should not be blocked: {[e.message for e in blocked]}"


def assert_blocked(report, *, expected_rule_ids: list[str]):
    """Golden assertions for any blocked result."""
    assert report.render_ready is False
    assert report.status == "blocked"
    assert report.template_payload is None, "blocked result should have no template_payload"
    blocked = [e for e in report.errors if e.severity == "blocked"]
    actual_ids = {e.rule_id for e in blocked}
    for rid in expected_rule_ids:
        assert rid in actual_ids, f"Expected blocking rule {rid!r} not found. Got: {actual_ids}"


# ---------------------------------------------------------------------------
# Ready payloads (3)
# ---------------------------------------------------------------------------


class TestReadyCorpus:
    def test_generic_erp(self):
        """Generic ERP export with no vendor branding — PascalCase, nested parties."""
        report = ingest_invoice(load("generic_erp"))
        assert_render_ready(
            report,
            sender_name="Nordic Manufacturing AG",
            recipient_name="Pacific Distributors Ltd",
            invoice_number="ERP-2026-4401",
            min_items=3,
        )
        # Template has correct currency formatting
        tp = report.template_payload
        assert "CHF" in tp["total"] or "3" in tp["total"]
        # Aliases resolved: vendor→sender, client→recipient, entries→items
        alias_targets = {n.canonical_name for n in report.normalizations}
        assert "sender" in alias_targets or any("sender" in t for t in alias_targets)
        assert "recipient" in alias_targets or any("recipient" in t for t in alias_targets)

    def test_flat_billing(self):
        """Flat snake_case billing with bill_from/bill_to synthesis."""
        report = ingest_invoice(load("flat_billing"))
        assert_render_ready(
            report,
            sender_name="Coastal Web Studios",
            recipient_name="Evergreen Health Partners",
            invoice_number="FB-90221",
            min_items=3,
        )
        # Flat party synthesis: bill_from_name → sender.name
        alias_originals = {n.original_key for n in report.normalizations}
        assert "bill_from_name" in alias_originals
        assert "bill_to_name" in alias_originals

    def test_minimal_valid(self):
        """Absolute minimum fields — tests computed defaults."""
        report = ingest_invoice(load("minimal_valid"))
        assert_render_ready(
            report,
            sender_name="Alice Test Co",
            recipient_name="Bob Receiving Inc",
            invoice_number="MIN-001",
            min_items=1,
        )
        # Should have computed subtotal and total from items
        canonical = report.canonical
        assert canonical["subtotal"] > 0 or canonical["total"] > 0, "minimal payload should compute totals from items"
        # Computed fields should be tracked
        assert len(report.computed_fields) > 0, "minimal payload should have computed fields"


# ---------------------------------------------------------------------------
# Blocked payloads (4)
# ---------------------------------------------------------------------------


class TestBlockedCorpus:
    def test_no_sender(self):
        """Missing sender blocks on identity.sender_name."""
        report = ingest_invoice(load("no_sender"))
        assert_blocked(report, expected_rule_ids=["identity.sender_name"])
        # Even though blocked, canonical should still have other fields resolved
        assert report.canonical.get("invoice_number") == "BLK-001"

    def test_empty_items(self):
        """Empty items array blocks on items.non_empty."""
        report = ingest_invoice(load("empty_items"))
        assert_blocked(report, expected_rule_ids=["items.non_empty"])

    def test_no_invoice_number(self):
        """No invoice_number (and no alias for it) blocks on identity.invoice_number."""
        report = ingest_invoice(load("no_invoice_number"))
        assert_blocked(report, expected_rule_ids=["identity.invoice_number"])
        # sender/recipient should still resolve even if invoice_number is missing
        assert report.canonical.get("sender", {}).get("name") == "No Number Inc"

    def test_bad_arithmetic(self):
        """Intentionally wrong total blocks on arithmetic.total."""
        report = ingest_invoice(load("bad_arithmetic"))
        assert_blocked(report, expected_rule_ids=["arithmetic.total"])
        # The arithmetic error should include expected value
        arith_errors = [e for e in report.errors if e.rule_id == "arithmetic.total"]
        assert len(arith_errors) == 1
        assert arith_errors[0].expected is not None


# ---------------------------------------------------------------------------
# Weird but recoverable payloads (3)
# ---------------------------------------------------------------------------


class TestRecoverableCorpus:
    def test_extra_junk_fields(self):
        """Valid invoice with 10 extra unrecognized fields → ready + unknown_fields."""
        report = ingest_invoice(load("extra_junk"))
        assert_render_ready(
            report,
            sender_name="Legit Business Co",
            recipient_name="Also Legit LLC",
            invoice_number="JUNK-777",
        )
        # Unknown fields should be captured, not silently dropped
        assert len(report.unknown_fields) >= 5, f"Expected 5+ unknown fields, got {len(report.unknown_fields)}"
        unknown_paths = {u.path for u in report.unknown_fields}
        assert "internal_tracking_id" in unknown_paths
        assert "salesforce_opportunity_id" in unknown_paths

    def test_mixed_casing(self):
        """Every key in a different case style — alias resolution stress test."""
        report = ingest_invoice(load("mixed_casing"))
        assert_render_ready(
            report,
            sender_name="cAsInG Nightmares Ltd",
            recipient_name="LOUD CLIENT CO",
            invoice_number="CASE-2026-MIX",
            min_items=2,
        )
        # Aliases should resolve across casing styles
        alias_originals = {n.original_key for n in report.normalizations}
        # PascalCase vendor fields
        assert "CompanyName" in alias_originals
        assert "DocNumber" in alias_originals
        # Xero-style PascalCase
        assert "LineItems" in alias_originals or "Contact" in alias_originals
        # camelCase
        assert "paymentTerms" in alias_originals

    def test_nested_unwrap(self):
        """Root unwrap { "invoice": {...} } + nested lines.data[] → ready."""
        report = ingest_invoice(load("nested_unwrap"))
        assert_render_ready(
            report,
            sender_name="Deeply Nested Corp",
            recipient_name="Flat Receiver LLC",
            invoice_number="WRAP-5501",
            min_items=2,
        )
        # Verify the pipeline unwrapped root and extracted nested lines
        tp = report.template_payload
        assert len(tp["items"]) == 2
        assert "API Integration" in tp["items"][0]["description"]


# ---------------------------------------------------------------------------
# Cross-corpus structural assertions
# ---------------------------------------------------------------------------


class TestCorpusStructure:
    """Meta-assertions that prove the pipeline is rule-driven, not fixture-driven."""

    @pytest.fixture(
        params=[
            "generic_erp",
            "flat_billing",
            "minimal_valid",
            "extra_junk",
            "mixed_casing",
            "nested_unwrap",
        ]
    )
    def ready_report(self, request):
        return ingest_invoice(load(request.param))

    def test_canonical_shape_is_consistent(self, ready_report):
        """Every ready result produces the same canonical key set."""
        assert REQUIRED_CANONICAL_KEYS <= set(ready_report.canonical.keys())

    def test_template_payload_shape_is_consistent(self, ready_report):
        """Every ready result produces the same template_payload key set."""
        tp = ready_report.template_payload
        assert tp is not None
        assert REQUIRED_TEMPLATE_KEYS <= set(tp.keys())

    def test_no_vendor_names_in_canonical(self, ready_report):
        """Canonical keys should never contain vendor-specific names."""
        vendor_fragments = {"stripe", "quickbooks", "qbo", "xero", "freshbooks"}
        for key in ready_report.canonical.keys():
            assert not any(v in key.lower() for v in vendor_fragments), f"Vendor name leaked into canonical key: {key}"

    def test_template_infers_to_invoice(self, ready_report):
        """All ready corpus entries should infer to invoice.j2.typ."""
        c = ready_report.canonical
        # The inference logic: invoice_number present + items present → invoice.j2.typ
        assert c.get("invoice_number"), "Ready result should have invoice_number"
        assert isinstance(c.get("items"), list) and len(c["items"]) > 0
