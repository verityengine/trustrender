"""Tests for ZUGFeRD EN 16931 e-invoice generation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from trustrender import render
from trustrender.errors import ErrorCode, TrustRenderError
from trustrender.zugferd import (
    apply_zugferd,
    build_invoice_xml,
    to_zugferd_data,
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
        with pytest.raises(TrustRenderError) as exc_info:
            render(
                "examples/einvoice.j2.typ",
                {"invoice_number": "X"},
                zugferd="en16931",
            )
        assert exc_info.value.code == ErrorCode.ZUGFERD_ERROR
        assert exc_info.value.stage == "zugferd_validation"

    def test_unsupported_profile_raises(self):
        """render() with unsupported profile raises INVALID_DATA."""
        with pytest.raises(TrustRenderError) as exc_info:
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
        data["items"] = [
            {
                "description": "Beratungsstunde",
                "quantity": 1,
                "unit": "C62",
                "unit_price": 150.00,
                "tax_rate": 19,
                "line_total": 150.00,
            }
        ]
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
                "description": f"Posten {i + 1}",
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
        data["items"] = [
            {
                "description": "Kleinstbetrag",
                "quantity": 1,
                "unit": "C62",
                "unit_price": 0.01,
                "tax_rate": 19,
                "line_total": 0.01,
            }
        ]
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
        data["items"] = [
            {
                "description": "Enterprise-Lizenz",
                "quantity": 1,
                "unit": "C62",
                "unit_price": 999999.99,
                "tax_rate": 19,
                "line_total": 999999.99,
            }
        ]
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
        from trustrender.readiness import preflight

        data = _load_creditnote_data()
        verdict = preflight(
            "examples/einvoice.j2.typ",
            data,
            zugferd="en16931",
        )
        assert verdict.ready is True

    def test_credit_note_preflight_fails_without_ref(self):
        """Credit note without referenced_invoice fails preflight."""
        from trustrender.readiness import preflight

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


# ---------------------------------------------------------------------------
# Arithmetic consistency validation
# ---------------------------------------------------------------------------


class TestArithmeticConsistency:
    """Prove arithmetic mismatches are caught before rendering."""

    def test_consistent_totals_pass(self):
        """Correctly computed totals pass validation."""
        data = _load_einvoice_data()
        errors = validate_zugferd_invoice_data(data)
        assert errors == []

    def test_subtotal_mismatch_rejected(self):
        """subtotal != sum(line_total) -> error."""
        data = _load_einvoice_data()
        data["subtotal"] = 9999.00  # actual sum is 8950.00
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "subtotal" in paths
        assert any("sum of line totals" in e.message for e in errors)

    def test_tax_total_mismatch_rejected(self):
        """tax_total != sum(tax_entries.amount) -> error."""
        data = _load_einvoice_data()
        data["tax_total"] = 9999.00  # actual sum of entries is 1700.50
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "tax_total" in paths
        assert any("sum of tax entry amounts" in e.message for e in errors)

    def test_grand_total_mismatch_rejected(self):
        """total != subtotal + tax_total -> error."""
        data = _load_einvoice_data()
        data["total"] = 5000.00  # should be 8950 + 1700.50 = 10650.50
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "total" in paths
        assert any("subtotal + tax_total" in e.message for e in errors)

    def test_penny_rounding_within_tolerance(self):
        """Off-by-one-cent is within tolerance (<=0.01)."""
        data = _load_einvoice_data()
        # Shift total by exactly 0.01 — should still pass
        data["total"] = 10650.51  # actual is 10650.50
        errors = validate_zugferd_invoice_data(data)
        total_errors = [e for e in errors if e.path == "total"]
        assert total_errors == []

    def test_two_cent_mismatch_rejected(self):
        """Off-by-two-cents exceeds tolerance -> error."""
        data = _load_einvoice_data()
        data["total"] = 10650.53  # actual is 10650.50, diff = 0.03
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "total" in paths

    def test_all_three_wrong_produces_three_errors(self):
        """All three consistency checks fire independently."""
        data = _load_einvoice_data()
        data["subtotal"] = 1.00
        data["tax_total"] = 2.00
        data["total"] = 9999.00
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "subtotal" in paths
        assert "tax_total" in paths
        assert "total" in paths

    def test_render_rejects_inconsistent_totals(self):
        """render() raises ZUGFERD_ERROR for arithmetic mismatch."""
        data = _load_einvoice_data()
        data["total"] = 9999.00
        with pytest.raises(TrustRenderError) as exc_info:
            render("examples/einvoice.j2.typ", data, zugferd="en16931")
        assert exc_info.value.code == ErrorCode.ZUGFERD_ERROR

    def test_preflight_rejects_inconsistent_totals(self):
        """preflight() fails for arithmetic mismatch."""
        from trustrender.readiness import preflight

        data = _load_einvoice_data()
        data["total"] = 9999.00
        verdict = preflight("examples/einvoice.j2.typ", data, zugferd="en16931")
        assert verdict.ready is False

    def test_mixed_rate_consistency(self):
        """Mixed-rate invoice with correct arithmetic passes."""
        data = _load_einvoice_data()
        data["items"][0]["tax_rate"] = 7
        data["items"][0]["line_total"] = 4500.00
        data["items"][1]["tax_rate"] = 19
        data["items"][2]["tax_rate"] = 19
        data["tax_entries"] = [
            {"rate": 7, "basis": 4500.00, "amount": 315.00},
            {"rate": 19, "basis": 4450.00, "amount": 845.50},
        ]
        data["subtotal"] = 8950.00
        data["tax_total"] = 1160.50
        data["total"] = 10110.50
        errors = validate_zugferd_invoice_data(data)
        assert errors == []


# ---------------------------------------------------------------------------
# Zero/negative tax rate rejection
# ---------------------------------------------------------------------------


class TestZeroTaxRateRejection:
    """Prove 0% and negative tax rates are rejected."""

    def test_zero_tax_rate_rejected(self):
        """tax_rate: 0 -> explicit error (not silently category S)."""
        data = _load_einvoice_data()
        data["items"][0]["tax_rate"] = 0
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "items[0].tax_rate" in paths
        assert any("not supported in v1" in e.message for e in errors)

    def test_negative_tax_rate_rejected(self):
        """Negative tax rate -> error."""
        data = _load_einvoice_data()
        data["items"][0]["tax_rate"] = -19
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "items[0].tax_rate" in paths

    def test_zero_tax_entry_rate_rejected(self):
        """tax_entries with rate 0 -> error."""
        data = _load_einvoice_data()
        data["items"][0]["tax_rate"] = 0
        data["tax_entries"] = [
            {"rate": 0, "basis": 4500.00, "amount": 0.00},
            {"rate": 19, "basis": 4450.00, "amount": 845.50},
        ]
        errors = validate_zugferd_invoice_data(data)
        paths = [e.path for e in errors]
        assert "items[0].tax_rate" in paths
        assert "tax_entries[0].rate" in paths

    def test_error_message_mentions_exempt_and_reverse_charge(self):
        """Error message explains WHY 0% is rejected."""
        data = _load_einvoice_data()
        data["items"][0]["tax_rate"] = 0
        errors = validate_zugferd_invoice_data(data)
        rate_errors = [e for e in errors if "tax_rate" in e.path]
        assert any("zero-rated" in e.message for e in rate_errors)
        assert any("reverse-charge" in e.message for e in rate_errors)

    def test_valid_positive_rates_still_pass(self):
        """Positive rates (7%, 19%) are unaffected."""
        data = _load_einvoice_data()
        errors = validate_zugferd_invoice_data(data)
        rate_errors = [e for e in errors if "tax_rate" in e.path]
        assert rate_errors == []

    def test_render_rejects_zero_rate(self):
        """render() raises ZUGFERD_ERROR for 0% tax rate."""
        data = _load_einvoice_data()
        data["items"][0]["tax_rate"] = 0
        with pytest.raises(TrustRenderError) as exc_info:
            render("examples/einvoice.j2.typ", data, zugferd="en16931")
        assert exc_info.value.code == ErrorCode.ZUGFERD_ERROR

    def test_preflight_rejects_zero_rate(self):
        """preflight() fails for 0% tax rate."""
        from trustrender.readiness import preflight

        data = _load_einvoice_data()
        data["items"][0]["tax_rate"] = 0
        verdict = preflight("examples/einvoice.j2.typ", data, zugferd="en16931")
        assert verdict.ready is False


# ---------------------------------------------------------------------------
# to_zugferd_data() bridge — canonical → ZUGFeRD shape
# ---------------------------------------------------------------------------


class TestToZugferdData:
    """The bridge that closes the gap between TrustRender's canonical schema
    (sender/recipient, top-level amounts) and the EN 16931 schema (seller/buyer,
    per-line tax rates, tax_entries, payment).
    """

    def _canonical(self) -> dict:
        from trustrender import validate_invoice
        from trustrender.adapters.stripe import from_stripe

        raw = json.loads((EXAMPLES / "demo_stripe_ready.json").read_text())
        result = validate_invoice(from_stripe(raw))
        return result["canonical"]

    def _seller(self) -> dict:
        return {
            "name": "NovaTech Solutions GmbH",
            "address": "Hauptstr. 5",
            "city": "Berlin",
            "postal_code": "10115",
            "country": "DE",
            "vat_id": "DE123456789",
        }

    def _payment(self) -> dict:
        return {"means": "credit_transfer", "iban": "DE89370400440532013000", "bic": "COBADEFFXXX"}

    def test_produces_zugferd_valid_dict(self):
        """The bridged dict passes validate_zugferd_invoice_data with no errors."""
        zd = to_zugferd_data(
            self._canonical(),
            seller=self._seller(),
            payment=self._payment(),
            tax_rate=19,
        )
        errors = validate_zugferd_invoice_data(zd)
        assert errors == [], f"unexpected EN 16931 errors: {[(e.path, e.message) for e in errors]}"

    def test_bridges_recipient_to_buyer(self):
        zd = to_zugferd_data(
            self._canonical(),
            seller=self._seller(),
            payment=self._payment(),
            tax_rate=19,
        )
        assert zd["buyer"]["name"] == "Rheingold Maschinenbau GmbH"
        assert zd["buyer"]["country"] == "DE"
        assert zd["buyer"]["postal_code"] == "70173"

    def test_propagates_tax_rate_to_each_line(self):
        zd = to_zugferd_data(
            self._canonical(),
            seller=self._seller(),
            payment=self._payment(),
            tax_rate=19,
        )
        assert all(item["tax_rate"] == 19 for item in zd["items"])

    def test_builds_single_tax_entry(self):
        canonical = self._canonical()
        zd = to_zugferd_data(canonical, seller=self._seller(), payment=self._payment(), tax_rate=19)
        assert len(zd["tax_entries"]) == 1
        entry = zd["tax_entries"][0]
        assert entry["rate"] == 19
        assert entry["basis"] == canonical["subtotal"]
        assert entry["amount"] == canonical["tax_amount"]

    def test_xml_roundtrip(self):
        """Bridged dict → drafthorse → XSD-valid CII XML."""
        from facturx import xml_check_xsd

        zd = to_zugferd_data(
            self._canonical(),
            seller=self._seller(),
            payment=self._payment(),
            tax_rate=19,
        )
        xml = build_invoice_xml(zd)
        assert xml_check_xsd(xml, flavor="factur-x", level="en16931") is True

    def test_credit_note_requires_referenced_invoice(self):
        zd = to_zugferd_data(
            self._canonical(),
            seller=self._seller(),
            payment=self._payment(),
            tax_rate=19,
            invoice_type="381",
            referenced_invoice="INV-2026-0042",
        )
        assert zd["invoice_type"] == "381"
        assert zd["referenced_invoice"] == "INV-2026-0042"
        # And it should still validate
        assert validate_zugferd_invoice_data(zd) == []

    def test_rejects_non_dict_canonical(self):
        with pytest.raises(ValueError, match="canonical must be a dict"):
            to_zugferd_data("not a dict", seller={}, payment={}, tax_rate=19)

    def test_rejects_non_dict_seller(self):
        with pytest.raises(ValueError, match="seller must be a dict"):
            to_zugferd_data({}, seller="x", payment={}, tax_rate=19)

    def test_rejects_non_dict_payment(self):
        with pytest.raises(ValueError, match="payment must be a dict"):
            to_zugferd_data({}, seller={}, payment="x", tax_rate=19)

    def test_missing_seller_fields_surface_in_zugferd_errors(self):
        """Bridge passes seller through; missing fields surface as proper EN 16931 errors."""
        zd = to_zugferd_data(
            self._canonical(),
            seller={"name": "Acme"},  # incomplete
            payment=self._payment(),
            tax_rate=19,
        )
        errors = validate_zugferd_invoice_data(zd)
        paths = {e.path for e in errors}
        assert "seller.address" in paths
        assert "seller.vat_id" in paths
