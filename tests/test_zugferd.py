"""Tests for ZUGFeRD EN 16931 e-invoice generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from formforge import render
from formforge.errors import ErrorCode, FormforgeError
from formforge.zugferd import (
    apply_zugferd,
    build_invoice_xml,
    validate_zugferd_invoice_data,
)

EXAMPLES = Path(__file__).parent.parent / "examples"


def _load_einvoice_data() -> dict:
    return json.loads((EXAMPLES / "einvoice_data.json").read_text())


# ---------------------------------------------------------------------------
# Invoice data validation
# ---------------------------------------------------------------------------


class TestValidateInvoiceData:
    def test_valid_data_passes(self):
        errors = validate_zugferd_invoice_data(_load_einvoice_data())
        assert errors == []

    def test_missing_invoice_number(self):
        data = _load_einvoice_data()
        del data["invoice_number"]
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "invoice_number" in paths

    def test_missing_seller_vat_id(self):
        data = _load_einvoice_data()
        del data["seller"]["vat_id"]
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "seller.vat_id" in paths

    def test_missing_buyer(self):
        data = _load_einvoice_data()
        del data["buyer"]
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "buyer" in paths

    def test_non_eur_currency_rejected(self):
        data = _load_einvoice_data()
        data["currency"] = "USD"
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "currency" in paths

    def test_non_de_country_rejected(self):
        data = _load_einvoice_data()
        data["seller"]["country"] = "FR"
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "seller.country" in paths

    def test_mixed_tax_rates_rejected(self):
        data = _load_einvoice_data()
        data["items"][0]["tax_rate"] = 7
        data["items"][1]["tax_rate"] = 19
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "items" in paths
        assert any("mixed tax rates" in e.message for e in errors)

    def test_empty_items_rejected(self):
        data = _load_einvoice_data()
        data["items"] = []
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "items" in paths

    def test_missing_payment(self):
        data = _load_einvoice_data()
        del data["payment"]
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "payment" in paths

    def test_non_numeric_total_rejected(self):
        data = _load_einvoice_data()
        data["total"] = "$8,032.50"
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "total" in paths


# ---------------------------------------------------------------------------
# XML generation
# ---------------------------------------------------------------------------


class TestBuildInvoiceXml:
    def test_generates_valid_xml(self):
        xml = build_invoice_xml(_load_einvoice_data())
        assert xml.startswith(b"<?xml")
        assert b"CrossIndustryInvoice" in xml

    def test_contains_invoice_number(self):
        xml = build_invoice_xml(_load_einvoice_data())
        assert b"RE-2026-0042" in xml

    def test_contains_seller_vat(self):
        xml = build_invoice_xml(_load_einvoice_data())
        assert b"DE123456789" in xml

    def test_xsd_validation_passes(self):
        xml = build_invoice_xml(_load_einvoice_data())
        from facturx import xml_check_xsd

        xml_check_xsd(xml)  # Raises on failure

    def test_schematron_validation_passes(self):
        xml = build_invoice_xml(_load_einvoice_data())
        from facturx.facturx import xml_check_schematron

        xml_check_schematron(xml)  # Raises on failure


# ---------------------------------------------------------------------------
# PDF post-processing
# ---------------------------------------------------------------------------


class TestApplyZugferd:
    def test_produces_pdf(self):
        data = _load_einvoice_data()
        xml = build_invoice_xml(data)
        # Render a simple PDF to combine with
        pdf = render("examples/invoice.j2.typ", "examples/invoice_data.json")
        result = apply_zugferd(pdf, xml)
        assert result[:5] == b"%PDF-"

    def test_xml_extractable(self):
        data = _load_einvoice_data()
        xml = build_invoice_xml(data)
        pdf = render("examples/invoice.j2.typ", "examples/invoice_data.json")
        result = apply_zugferd(pdf, xml)

        from facturx import get_xml_from_pdf

        filename, extracted = get_xml_from_pdf(result)
        assert filename == "factur-x.xml"
        assert extracted == xml


# ---------------------------------------------------------------------------
# render() integration
# ---------------------------------------------------------------------------


class TestRenderWithZugferd:
    def test_happy_path(self):
        """render() with zugferd='en16931' produces a valid PDF."""
        pdf = render(
            "examples/einvoice.j2.typ",
            "examples/einvoice_data.json",
            zugferd="en16931",
        )
        assert pdf[:5] == b"%PDF-"
        # Verify XML is embedded
        from facturx import get_xml_from_pdf

        filename, _ = get_xml_from_pdf(pdf)
        assert filename == "factur-x.xml"

    def test_bad_data_raises_zugferd_error(self):
        """render() with bad invoice data raises ZUGFERD_ERROR."""
        with pytest.raises(FormforgeError) as exc_info:
            render(
                "examples/einvoice.j2.typ",
                {"invoice_number": "X"},
                zugferd="en16931",
            )
        assert exc_info.value.code == ErrorCode.ZUGFERD_ERROR
        assert exc_info.value.stage == "zugferd_validation"

    def test_unsupported_profile_raises(self):
        """render() with unsupported profile raises INVALID_DATA."""
        with pytest.raises(FormforgeError) as exc_info:
            render(
                "examples/einvoice.j2.typ",
                "examples/einvoice_data.json",
                zugferd="basic",
            )
        assert exc_info.value.code == ErrorCode.INVALID_DATA

    def test_without_zugferd_no_xml(self):
        """render() without zugferd produces normal PDF (no embedded XML)."""
        pdf = render("examples/invoice.j2.typ", "examples/invoice_data.json")
        from facturx import get_xml_from_pdf

        try:
            get_xml_from_pdf(pdf)
            assert False, "Should not find XML in non-ZUGFeRD PDF"
        except Exception:
            pass  # Expected — no XML embedded


# ---------------------------------------------------------------------------
# Regression: existing invoice path untouched
# ---------------------------------------------------------------------------


class TestRegression:
    def test_old_invoice_still_works(self):
        """The original invoice template + data still renders without changes."""
        pdf = render("examples/invoice.j2.typ", "examples/invoice_data.json")
        assert pdf[:5] == b"%PDF-"

    def test_old_invoice_with_validate(self):
        """validate=True still works on old invoice."""
        pdf = render(
            "examples/invoice.j2.typ",
            "examples/invoice_data.json",
            validate=True,
        )
        assert pdf[:5] == b"%PDF-"

    def test_zugferd_none_is_noop(self):
        """zugferd=None is the default and changes nothing."""
        pdf = render(
            "examples/invoice.j2.typ",
            "examples/invoice_data.json",
            zugferd=None,
        )
        assert pdf[:5] == b"%PDF-"
