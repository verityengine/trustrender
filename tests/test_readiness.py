"""Tests for pre-render readiness verification."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from formforge.readiness import preflight

EXAMPLES = Path(__file__).parent.parent / "examples"


def _load_data(name: str) -> dict:
    return json.loads((EXAMPLES / f"{name}_data.json").read_text())


class TestPreflightHappyPath:
    def test_invoice_passes(self):
        verdict = preflight(EXAMPLES / "invoice.j2.typ", _load_data("invoice"))
        assert verdict.ready is True
        assert len(verdict.errors) == 0

    def test_einvoice_passes(self):
        verdict = preflight(EXAMPLES / "einvoice.j2.typ", _load_data("einvoice"))
        assert verdict.ready is True

    def test_statement_passes(self):
        verdict = preflight(EXAMPLES / "statement.j2.typ", _load_data("statement"))
        assert verdict.ready is True

    def test_receipt_passes(self):
        verdict = preflight(EXAMPLES / "receipt.j2.typ", _load_data("receipt"))
        assert verdict.ready is True

    def test_letter_passes(self):
        verdict = preflight(EXAMPLES / "letter.j2.typ", _load_data("letter"))
        assert verdict.ready is True

    def test_report_passes(self):
        verdict = preflight(EXAMPLES / "report.j2.typ", _load_data("report"))
        assert verdict.ready is True


class TestPreflightPayload:
    def test_empty_data_fails(self):
        verdict = preflight(EXAMPLES / "invoice.j2.typ", {})
        assert verdict.ready is False
        assert len(verdict.errors) > 0
        assert all(e.stage == "payload" for e in verdict.errors)

    def test_missing_field_reported(self):
        data = _load_data("invoice")
        del data["sender"]
        verdict = preflight(EXAMPLES / "invoice.j2.typ", data)
        assert verdict.ready is False
        paths = [e.path for e in verdict.errors]
        assert "sender" in paths

    def test_extra_fields_allowed(self):
        data = _load_data("invoice")
        data["completely_unknown"] = "hello"
        verdict = preflight(EXAMPLES / "invoice.j2.typ", data)
        assert verdict.ready is True


class TestPreflightTemplate:
    def test_missing_template_fails(self):
        verdict = preflight("nonexistent.j2.typ", {})
        assert verdict.ready is False
        assert any(e.check == "template_not_found" for e in verdict.errors)

    def test_stages_tracked(self):
        verdict = preflight(EXAMPLES / "invoice.j2.typ", _load_data("invoice"))
        assert "payload" in verdict.stages_checked
        assert "template" in verdict.stages_checked
        assert "environment" in verdict.stages_checked


class TestPreflightCompliance:
    def test_en16931_eligible(self):
        verdict = preflight(
            EXAMPLES / "einvoice.j2.typ",
            _load_data("einvoice"),
            zugferd="en16931",
        )
        assert verdict.ready is True
        assert "en16931" in verdict.profile_eligible
        assert "compliance" in verdict.stages_checked

    def test_xrechnung_missing_fields(self):
        verdict = preflight(
            EXAMPLES / "einvoice.j2.typ",
            _load_data("einvoice"),
            zugferd="xrechnung",
        )
        assert verdict.ready is False
        paths = [e.path for e in verdict.errors]
        assert "buyer_reference" in paths

    def test_profile_eligibility_report(self):
        verdict = preflight(
            EXAMPLES / "einvoice.j2.typ",
            _load_data("einvoice"),
            zugferd="en16931",
        )
        assert "en16931" in verdict.profile_eligible
        assert "xrechnung" not in verdict.profile_eligible

    def test_non_eur_currency_fails(self):
        data = _load_data("einvoice")
        data["currency"] = "USD"
        verdict = preflight(
            EXAMPLES / "einvoice.j2.typ", data, zugferd="en16931",
        )
        assert verdict.ready is False
        assert any("USD" in e.message for e in verdict.errors)


class TestPreflightEnvironment:
    def test_environment_checked(self):
        verdict = preflight(EXAMPLES / "invoice.j2.typ", _load_data("invoice"))
        assert "environment" in verdict.stages_checked


class TestPreflightRegression:
    def test_does_not_render(self):
        """preflight() should NOT produce a PDF — it's a dry run."""
        verdict = preflight(EXAMPLES / "invoice.j2.typ", _load_data("invoice"))
        # The verdict has no pdf_bytes attribute
        assert not hasattr(verdict, "pdf_bytes")
        assert isinstance(verdict.ready, bool)
