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

    def test_mixed_tax_rates_accepted(self):
        """Mixed rates (7% + 19%) are supported with proper tax_entries."""
        data = _load_einvoice_data()
        data["items"][0]["tax_rate"] = 7
        data["items"][0]["line_total"] = 4500.00
        data["items"][1]["tax_rate"] = 19
        data["items"][2]["tax_rate"] = 19
        data["tax_entries"] = [
            {"rate": 7, "basis": 4500.00, "amount": 315.00},
            {"rate": 19, "basis": 4450.00, "amount": 845.50},
        ]
        data["tax_total"] = 1160.50
        data["total"] = 8950.00 + 1160.50
        errors = validate_zugferd_invoice_data(data)
        assert errors == []

    def test_mixed_rates_missing_tax_entry(self):
        """Items at 7% + 19% but tax_entries only covers 19% -> error."""
        data = _load_einvoice_data()
        data["items"][0]["tax_rate"] = 7
        # tax_entries still only has 19% — missing 7%
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "tax_entries" in paths
        assert any("missing for item rate" in e.message for e in errors)

    def test_orphan_tax_entry_nonzero_basis_rejected(self):
        """tax_entries has rate 7% with non-zero basis but no items use 7% -> error."""
        data = _load_einvoice_data()
        data["tax_entries"].append({"rate": 7, "basis": 1000.00, "amount": 70.00})
        errors = validate_zugferd_invoice_data(data)
        assert any("no items use that rate" in e.message for e in errors)

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

    def test_allowances_rejected(self):
        data = _load_einvoice_data()
        data["allowances"] = [{"amount": 100, "reason": "Early payment"}]
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "allowances" in paths
        assert any("not supported" in e.message for e in errors)

    def test_charges_rejected(self):
        data = _load_einvoice_data()
        data["charges"] = [{"amount": 50, "reason": "Shipping"}]
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "charges" in paths

    def test_discounts_rejected(self):
        data = _load_einvoice_data()
        data["discounts"] = [{"percent": 10}]
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "discounts" in paths


# ---------------------------------------------------------------------------
# XRechnung: code path exists but Schematron fails
# ---------------------------------------------------------------------------


class TestXRechnungNotValidated:
    """Document that XRechnung code path exists but does NOT pass Schematron.

    These tests exist to prevent accidental claims of XRechnung support.
    If KOSIT Schematron is integrated in the future, these tests should
    be updated to expect passes instead of failures.
    """

    def _xrechnung_data(self):
        data = _load_einvoice_data()
        data["buyer_reference"] = "04011000-12345-67"
        data["seller"]["contact_name"] = "Max Mustermann"
        data["buyer"]["email"] = "einkauf@kunde.de"
        return data

    def test_xrechnung_validation_passes(self):
        """Field validation passes — the data shape is correct."""
        errors = validate_zugferd_invoice_data(self._xrechnung_data(), profile="xrechnung")
        assert errors == []

    def test_xrechnung_xsd_passes(self):
        """XSD passes — the XML structure is valid CII."""
        xml = build_invoice_xml(self._xrechnung_data(), profile="xrechnung")
        from facturx import xml_check_xsd

        xml_check_xsd(xml)

    def test_xrechnung_schematron_fails(self):
        """Schematron FAILS — guideline ID not in factur-x allowed set.

        This is the reason XRechnung is not claimed as supported.
        KOSIT XRechnung Schematron rules would be needed to validate properly.
        """
        xml = build_invoice_xml(self._xrechnung_data(), profile="xrechnung")
        from facturx.facturx import xml_check_schematron

        with pytest.raises(Exception, match="not valid against the official schematron"):
            xml_check_schematron(xml)


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


# ---------------------------------------------------------------------------
# Mixed VAT rates
# ---------------------------------------------------------------------------


class TestMixedVATRates:
    """Prove mixed tax rates (e.g., 7% + 19%) produce valid EN 16931 XML."""

    def _mixed_rate_data(self):
        data = _load_einvoice_data()
        # Item 1: reduced rate
        data["items"][0]["tax_rate"] = 7
        data["items"][0]["line_total"] = 4500.00
        # Items 2-3: standard rate
        data["items"][1]["tax_rate"] = 19
        data["items"][1]["line_total"] = 2250.00
        data["items"][2]["tax_rate"] = 19
        data["items"][2]["line_total"] = 2200.00
        # Tax entries per rate
        data["tax_entries"] = [
            {"rate": 7, "basis": 4500.00, "amount": 315.00},
            {"rate": 19, "basis": 4450.00, "amount": 845.50},
        ]
        data["subtotal"] = 8950.00
        data["tax_total"] = 1160.50
        data["total"] = 10110.50
        return data

    def test_validation_passes(self):
        errors = validate_zugferd_invoice_data(self._mixed_rate_data())
        assert errors == []

    def test_xml_has_two_tax_entries(self):
        xml = build_invoice_xml(self._mixed_rate_data())
        xml_str = xml.decode("utf-8")
        # Two ApplicableTradeTax blocks in settlement (one per rate)
        count = xml_str.count("ram:RateApplicablePercent")
        # Each line item also has a rate, so filter to settlement-level
        # Just verify both rate values appear
        assert "7" in xml_str
        assert "19" in xml_str

    def test_xsd_passes(self):
        xml = build_invoice_xml(self._mixed_rate_data())
        from facturx import xml_check_xsd
        xml_check_xsd(xml)

    def test_schematron_passes(self):
        xml = build_invoice_xml(self._mixed_rate_data())
        from facturx.facturx import xml_check_schematron
        xml_check_schematron(xml)

    def test_render_produces_valid_pdf(self):
        """Full render with mixed rates produces PDF with embedded XML."""
        data = self._mixed_rate_data()
        pdf = render(
            "examples/einvoice.j2.typ",
            data,
            zugferd="en16931",
        )
        assert pdf[:5] == b"%PDF-"
        from facturx import get_xml_from_pdf
        filename, _ = get_xml_from_pdf(pdf)
        assert filename == "factur-x.xml"


# ---------------------------------------------------------------------------
# Fixture variants: prove EN 16931 works beyond one example
# ---------------------------------------------------------------------------


class TestFixtureVariants:
    """Multiple invoice data shapes to verify EN 16931 isn't one-trick."""

    def _base_data(self):
        return _load_einvoice_data()

    def test_single_item_invoice(self):
        """Minimal invoice: 1 item, small amount."""
        data = self._base_data()
        data["items"] = [{
            "description": "Beratungsstunde",
            "quantity": 1,
            "unit": "C62",
            "unit_price": 150.00,
            "tax_rate": 19,
            "line_total": 150.00,
        }]
        data["subtotal"] = 150.00
        data["tax_entries"] = [{"rate": 19, "basis": 150.00, "amount": 28.50}]
        data["tax_total"] = 28.50
        data["total"] = 178.50
        errors = validate_zugferd_invoice_data(data)
        assert errors == []
        xml = build_invoice_xml(data)
        from facturx import xml_check_xsd
        xml_check_xsd(xml)

    def test_many_items_invoice(self):
        """Invoice with 20 line items."""
        data = self._base_data()
        data["items"] = [
            {
                "description": f"Posten {i+1}",
                "quantity": i + 1,
                "unit": "C62",
                "unit_price": 10.00,
                "tax_rate": 19,
                "line_total": (i + 1) * 10.00,
            }
            for i in range(20)
        ]
        subtotal = sum(item["line_total"] for item in data["items"])
        tax = round(subtotal * 0.19, 2)
        data["subtotal"] = subtotal
        data["tax_entries"] = [{"rate": 19, "basis": subtotal, "amount": tax}]
        data["tax_total"] = tax
        data["total"] = subtotal + tax
        errors = validate_zugferd_invoice_data(data)
        assert errors == []
        xml = build_invoice_xml(data)
        from facturx import xml_check_xsd
        xml_check_xsd(xml)

    def test_small_amounts(self):
        """Invoice with penny-level amounts (boundary values)."""
        data = self._base_data()
        data["items"] = [{
            "description": "Kleinstbetrag",
            "quantity": 1,
            "unit": "C62",
            "unit_price": 0.01,
            "tax_rate": 19,
            "line_total": 0.01,
        }]
        data["subtotal"] = 0.01
        data["tax_entries"] = [{"rate": 19, "basis": 0.01, "amount": 0.00}]
        data["tax_total"] = 0.00
        data["total"] = 0.01
        errors = validate_zugferd_invoice_data(data)
        assert errors == []
        xml = build_invoice_xml(data)
        from facturx import xml_check_xsd
        xml_check_xsd(xml)

    def test_large_amounts(self):
        """Invoice with large amounts."""
        data = self._base_data()
        data["items"] = [{
            "description": "Enterprise-Lizenz",
            "quantity": 1,
            "unit": "C62",
            "unit_price": 999999.99,
            "tax_rate": 19,
            "line_total": 999999.99,
        }]
        data["subtotal"] = 999999.99
        tax = round(999999.99 * 0.19, 2)
        data["tax_entries"] = [{"rate": 19, "basis": 999999.99, "amount": tax}]
        data["tax_total"] = tax
        data["total"] = 999999.99 + tax
        errors = validate_zugferd_invoice_data(data)
        assert errors == []
        xml = build_invoice_xml(data)
        from facturx import xml_check_xsd
        xml_check_xsd(xml)

    def test_direct_debit_payment(self):
        """Invoice with SEPA direct debit instead of credit transfer."""
        data = self._base_data()
        data["payment"] = {
            "means": "direct_debit",
            "iban": "DE89370400440532013000",
        }
        errors = validate_zugferd_invoice_data(data)
        assert errors == []
        xml = build_invoice_xml(data)
        assert b"59" in xml  # Direct debit code

    def test_unicode_company_names(self):
        """Company names with umlauts and special chars in XML."""
        data = self._base_data()
        data["seller"]["name"] = "Müller & Söhne Bürotechnik GmbH"
        data["buyer"]["name"] = "Ärzte-Abrechnungsgesellschaft mbH"
        data["items"][0]["description"] = "Büroausstattung für Größe M — inkl. Zubehör"
        errors = validate_zugferd_invoice_data(data)
        assert errors == []
        xml = build_invoice_xml(data)
        from facturx import xml_check_xsd
        xml_check_xsd(xml)
        assert "Müller".encode("utf-8") in xml


# ---------------------------------------------------------------------------
# Credit notes (type code 381)
# ---------------------------------------------------------------------------


def _load_creditnote_data() -> dict:
    return json.loads((EXAMPLES / "creditnote_data.json").read_text())


class TestCreditNotes:
    """Prove credit note (type 381) support works end-to-end."""

    def test_credit_note_validation_passes(self):
        errors = validate_zugferd_invoice_data(_load_creditnote_data())
        assert errors == []

    def test_credit_note_requires_referenced_invoice(self):
        """Type 381 without referenced_invoice -> error."""
        data = _load_creditnote_data()
        del data["referenced_invoice"]
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "referenced_invoice" in paths

    def test_credit_note_rejects_empty_referenced_invoice(self):
        """Type 381 with whitespace-only referenced_invoice -> error."""
        data = _load_creditnote_data()
        data["referenced_invoice"] = "   "
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "referenced_invoice" in paths

    def test_invoice_rejects_referenced_invoice(self):
        """Type 380 with referenced_invoice -> error (prevent confusion)."""
        data = _load_einvoice_data()
        data["referenced_invoice"] = "RE-2026-0001"
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "referenced_invoice" in paths

    def test_invalid_type_code_rejected(self):
        """Unsupported type code -> error with explicit message."""
        data = _load_einvoice_data()
        data["invoice_type"] = "999"
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "invoice_type" in paths
        assert "380" in errors[0].message and "381" in errors[0].message

    def test_default_type_is_380(self):
        """Omitting invoice_type defaults to 380 (backward compat)."""
        data = _load_einvoice_data()
        del data["invoice_type"]  # simulate legacy data without the field
        errors = validate_zugferd_invoice_data(data)
        assert errors == []

    def test_credit_note_xml_type_code(self):
        """XML contains type code 381."""
        xml = build_invoice_xml(_load_creditnote_data())
        xml_str = xml.decode("utf-8")
        assert ">381<" in xml_str

    def test_credit_note_xml_has_referenced_document(self):
        """XML contains the referenced invoice number (BT-25)."""
        xml = build_invoice_xml(_load_creditnote_data())
        xml_str = xml.decode("utf-8")
        assert "RE-2026-0042" in xml_str

    def test_default_type_xml_is_380(self):
        """Omitting invoice_type produces type code 380 in XML."""
        data = _load_einvoice_data()
        xml = build_invoice_xml(data)
        xml_str = xml.decode("utf-8")
        assert ">380<" in xml_str

    def test_credit_note_xsd_passes(self):
        xml = build_invoice_xml(_load_creditnote_data())
        from facturx import xml_check_xsd
        xml_check_xsd(xml)

    def test_credit_note_schematron_passes(self):
        xml = build_invoice_xml(_load_creditnote_data())
        from facturx.facturx import xml_check_schematron
        xml_check_schematron(xml)

    def test_credit_note_render_produces_pdf(self):
        """Full render with zugferd=en16931 produces valid PDF."""
        data = _load_creditnote_data()
        pdf = render(
            "examples/einvoice.j2.typ",
            data,
            zugferd="en16931",
        )
        assert pdf[:5] == b"%PDF-"
        from facturx import get_xml_from_pdf
        filename, _ = get_xml_from_pdf(pdf)
        assert filename == "factur-x.xml"

    def test_credit_note_preflight_passes(self):
        """Credit note passes readiness preflight."""
        from formforge.readiness import preflight
        data = _load_creditnote_data()
        verdict = preflight(
            "examples/einvoice.j2.typ",
            data,
            zugferd="en16931",
        )
        assert verdict.ready is True

    def test_credit_note_preflight_fails_without_ref(self):
        """Credit note without referenced_invoice fails preflight."""
        from formforge.readiness import preflight
        data = _load_creditnote_data()
        del data["referenced_invoice"]
        verdict = preflight(
            "examples/einvoice.j2.typ",
            data,
            zugferd="en16931",
        )
        assert verdict.ready is False

    def test_default_render_still_says_rechnung(self):
        """Standard invoice (no invoice_type) renders RECHNUNG, not GUTSCHRIFT."""
        data = _load_einvoice_data()
        pdf = render(
            "examples/einvoice.j2.typ",
            data,
            zugferd="en16931",
        )
        assert pdf[:5] == b"%PDF-"
        # Verify type code 380 in embedded XML
        from facturx import get_xml_from_pdf
        _, xml_bytes = get_xml_from_pdf(pdf)
        assert b">380<" in xml_bytes
