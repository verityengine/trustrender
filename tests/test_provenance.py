"""Tests for document generation proof (provenance)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from formforge import render
from formforge.provenance import (
    create_provenance,
    embed_provenance,
    extract_provenance,
    verify_provenance,
)

EXAMPLES = Path(__file__).parent.parent / "examples"


def _load_invoice_data() -> dict:
    return json.loads((EXAMPLES / "invoice_data.json").read_text())


class TestCreateProvenance:
    def test_creates_record(self):
        record = create_provenance(EXAMPLES / "invoice.j2.typ", _load_invoice_data())
        assert record.engine == "formforge"
        assert record.engine_version == "0.1.0"
        assert record.template_name == "invoice.j2.typ"
        assert record.template_hash.startswith("sha256:")
        assert record.data_hash.startswith("sha256:")
        assert record.proof.startswith("sha256:")
        assert record.timestamp

    def test_same_inputs_same_hashes(self):
        data = _load_invoice_data()
        r1 = create_provenance(EXAMPLES / "invoice.j2.typ", data)
        r2 = create_provenance(EXAMPLES / "invoice.j2.typ", data)
        assert r1.template_hash == r2.template_hash
        assert r1.data_hash == r2.data_hash
        # Proof differs because timestamp differs

    def test_different_data_different_hash(self):
        data1 = _load_invoice_data()
        data2 = {**data1, "invoice_number": "DIFFERENT"}
        r1 = create_provenance(EXAMPLES / "invoice.j2.typ", data1)
        r2 = create_provenance(EXAMPLES / "invoice.j2.typ", data2)
        assert r1.data_hash != r2.data_hash


class TestEmbedExtract:
    def test_round_trip(self):
        pdf = render("examples/invoice.j2.typ", "examples/invoice_data.json")
        record = create_provenance(EXAMPLES / "invoice.j2.typ", _load_invoice_data())
        pdf_with_prov = embed_provenance(pdf, record)

        extracted = extract_provenance(pdf_with_prov)
        assert extracted is not None
        assert extracted.engine == record.engine
        assert extracted.template_hash == record.template_hash
        assert extracted.data_hash == record.data_hash
        assert extracted.proof == record.proof

    def test_no_provenance_returns_none(self):
        pdf = render("examples/invoice.j2.typ", "examples/invoice_data.json")
        assert extract_provenance(pdf) is None


class TestVerify:
    def test_correct_inputs_verified(self):
        data = _load_invoice_data()
        pdf = render("examples/invoice.j2.typ", data, provenance=True)
        result = verify_provenance(pdf, EXAMPLES / "invoice.j2.typ", data)
        assert result.verified is True
        assert result.reason == "match"

    def test_tampered_data_detected(self):
        data = _load_invoice_data()
        pdf = render("examples/invoice.j2.typ", data, provenance=True)
        tampered = {**data, "invoice_number": "TAMPERED"}
        result = verify_provenance(pdf, EXAMPLES / "invoice.j2.typ", tampered)
        assert result.verified is False
        assert result.reason == "data_mismatch"

    def test_wrong_template_detected(self):
        data = _load_invoice_data()
        pdf = render("examples/invoice.j2.typ", data, provenance=True)
        result = verify_provenance(pdf, EXAMPLES / "statement.j2.typ", data)
        assert result.verified is False
        assert result.reason == "template_mismatch"

    def test_no_provenance_detected(self):
        data = _load_invoice_data()
        pdf = render("examples/invoice.j2.typ", data)
        result = verify_provenance(pdf, EXAMPLES / "invoice.j2.typ", data)
        assert result.verified is False
        assert result.reason == "no_provenance"


class TestRenderIntegration:
    def test_provenance_flag(self):
        pdf = render("examples/invoice.j2.typ", "examples/invoice_data.json", provenance=True)
        record = extract_provenance(pdf)
        assert record is not None
        assert record.template_name == "invoice.j2.typ"

    def test_provenance_with_zugferd(self):
        """provenance + zugferd work together."""
        pdf = render(
            "examples/einvoice.j2.typ",
            "examples/einvoice_data.json",
            zugferd="en16931",
            provenance=True,
        )
        record = extract_provenance(pdf)
        assert record is not None
        assert record.template_name == "einvoice.j2.typ"

    def test_provenance_default_off(self):
        pdf = render("examples/invoice.j2.typ", "examples/invoice_data.json")
        assert extract_provenance(pdf) is None


class TestProvenanceWithZugferd:
    """Regression: provenance + ZUGFeRD must coexist without corruption."""

    def test_zugferd_plus_provenance_both_survive(self):
        """All three: render + ZUGFeRD + provenance. All must be present."""
        data = json.loads((EXAMPLES / "einvoice_data.json").read_text())
        pdf = render(
            "examples/einvoice.j2.typ", data,
            zugferd="en16931", provenance=True,
        )
        assert pdf[:5] == b"%PDF-"

        # Provenance must be extractable
        record = extract_provenance(pdf)
        assert record is not None
        assert record.template_name == "einvoice.j2.typ"

        # ZUGFeRD XML must be extractable
        from facturx import get_xml_from_pdf
        filename, xml = get_xml_from_pdf(pdf)
        assert filename == "factur-x.xml"
        assert len(xml) > 100
        assert b"CrossIndustryInvoice" in xml

    def test_provenance_verifies_after_zugferd(self):
        """Provenance verification works on ZUGFeRD PDFs."""
        data = json.loads((EXAMPLES / "einvoice_data.json").read_text())
        pdf = render(
            "examples/einvoice.j2.typ", data,
            zugferd="en16931", provenance=True,
        )
        result = verify_provenance(pdf, EXAMPLES / "einvoice.j2.typ", data)
        assert result.verified is True
        assert result.reason == "match"


class TestRegression:
    def test_old_invoice_no_provenance(self):
        """Default render unchanged — no provenance embedded."""
        pdf = render("examples/invoice.j2.typ", "examples/invoice_data.json")
        assert pdf[:5] == b"%PDF-"
        assert extract_provenance(pdf) is None
