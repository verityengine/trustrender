"""Tests for baseline drift detection."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from trustrender import render
from trustrender.fingerprint import compute_fingerprint
from trustrender.regression import (
    DriftBaseline,
    DriftResult,
    _SCHEMA_VERSION,
    _extract_embedded_fonts,
    check_drift,
    load_baseline,
    save_baseline,
)

EXAMPLES = Path(__file__).parent.parent / "examples"


def _load_data(name: str = "invoice_data.json") -> dict:
    return json.loads((EXAMPLES / name).read_text())


def _render_invoice(data: dict | None = None) -> bytes:
    if data is None:
        data = _load_data()
    return render(EXAMPLES / "invoice.j2.typ", data)


class TestSaveAndLoadBaseline:
    def test_save_creates_file(self, tmp_path):
        data = _load_data()
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        pdf = _render_invoice(data)

        bl = save_baseline(tmp_path, "invoice.j2.typ", fp, pdf)
        assert bl.schema_version == _SCHEMA_VERSION
        assert bl.template_file == "invoice.j2.typ"
        assert bl.pdf_size == len(pdf)
        assert bl.render_success is True
        assert bl.page_count is not None
        assert bl.page_count >= 1

        # File exists on disk
        latest = tmp_path / "invoice.j2.typ" / "latest.json"
        assert latest.exists()

    def test_load_returns_saved(self, tmp_path):
        data = _load_data()
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        pdf = _render_invoice(data)
        save_baseline(tmp_path, "invoice.j2.typ", fp, pdf)

        loaded = load_baseline(tmp_path, "invoice.j2.typ")
        assert loaded is not None
        assert loaded.template_file == "invoice.j2.typ"
        assert loaded.pdf_size == len(pdf)

    def test_load_returns_none_when_missing(self, tmp_path):
        assert load_baseline(tmp_path, "nonexistent.j2.typ") is None

    def test_baseline_serialization_roundtrip(self, tmp_path):
        data = _load_data()
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        pdf = _render_invoice(data)
        bl = save_baseline(
            tmp_path, "invoice.j2.typ", fp, pdf,
            render_duration_ms=150,
            zugferd_valid=None,
            contract_valid=True,
            semantic_issue_count=0,
        )
        d = bl.to_dict()
        bl2 = DriftBaseline.from_dict(d)
        assert bl2.pdf_size == bl.pdf_size
        assert bl2.page_count == bl.page_count
        assert bl2.schema_version == _SCHEMA_VERSION

    def test_schema_version_in_file(self, tmp_path):
        data = _load_data()
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        pdf = _render_invoice(data)
        save_baseline(tmp_path, "invoice.j2.typ", fp, pdf)

        raw = json.loads((tmp_path / "invoice.j2.typ" / "latest.json").read_text())
        assert raw["schema_version"] == _SCHEMA_VERSION


class TestDriftChecks:
    def test_no_drift_same_render(self, tmp_path):
        """Same inputs, same render — no drift."""
        data = _load_data()
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        pdf = _render_invoice(data)
        save_baseline(tmp_path, "invoice.j2.typ", fp, pdf)

        result = check_drift(tmp_path, "invoice.j2.typ", fp, pdf)
        assert result is not None
        assert result.passed
        assert not result.has_errors
        assert not result.has_warnings

    def test_returns_none_no_baseline(self, tmp_path):
        data = _load_data()
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        pdf = _render_invoice(data)
        result = check_drift(tmp_path, "invoice.j2.typ", fp, pdf)
        assert result is None

    def test_page_count_drift_warns(self, tmp_path):
        """Simulated page count change via baseline manipulation."""
        data = _load_data()
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        pdf = _render_invoice(data)
        bl = save_baseline(tmp_path, "invoice.j2.typ", fp, pdf)

        # Fake a baseline with different page count
        raw = json.loads((tmp_path / "invoice.j2.typ" / "latest.json").read_text())
        raw["page_count"] = (raw["page_count"] or 1) + 2
        (tmp_path / "invoice.j2.typ" / "latest.json").write_text(
            json.dumps(raw, indent=2)
        )

        result = check_drift(tmp_path, "invoice.j2.typ", fp, pdf)
        assert result is not None
        page_findings = [f for f in result.findings if f.check_name == "page_count_change"]
        assert len(page_findings) == 1
        assert page_findings[0].severity == "warning"
        assert page_findings[0].deterministic is True

    def test_page_count_large_drift_errors(self, tmp_path):
        data = _load_data()
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        pdf = _render_invoice(data)
        save_baseline(tmp_path, "invoice.j2.typ", fp, pdf)

        raw = json.loads((tmp_path / "invoice.j2.typ" / "latest.json").read_text())
        raw["page_count"] = (raw["page_count"] or 1) + 10
        (tmp_path / "invoice.j2.typ" / "latest.json").write_text(
            json.dumps(raw, indent=2)
        )

        result = check_drift(tmp_path, "invoice.j2.typ", fp, pdf)
        assert result.has_errors

    def test_file_size_drift_warns(self, tmp_path):
        data = _load_data()
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        pdf = _render_invoice(data)
        save_baseline(tmp_path, "invoice.j2.typ", fp, pdf)

        # Fake baseline with very different file size
        raw = json.loads((tmp_path / "invoice.j2.typ" / "latest.json").read_text())
        raw["pdf_size"] = len(pdf) * 3  # 200% larger baseline
        (tmp_path / "invoice.j2.typ" / "latest.json").write_text(
            json.dumps(raw, indent=2)
        )

        result = check_drift(tmp_path, "invoice.j2.typ", fp, pdf)
        size_findings = [
            f for f in result.findings
            if f.check_name in ("file_size_drift", "file_size_spike")
        ]
        assert len(size_findings) >= 1

    def test_render_failure_drift(self, tmp_path):
        data = _load_data()
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        pdf = _render_invoice(data)
        save_baseline(tmp_path, "invoice.j2.typ", fp, pdf)

        # Simulate render failure
        result = check_drift(
            tmp_path, "invoice.j2.typ", fp, b"",
            render_success=False,
        )
        render_findings = [f for f in result.findings if f.check_name == "render_success"]
        assert len(render_findings) == 1
        assert render_findings[0].severity == "error"

    def test_contract_status_change(self, tmp_path):
        data = _load_data()
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        pdf = _render_invoice(data)
        save_baseline(
            tmp_path, "invoice.j2.typ", fp, pdf,
            contract_valid=True,
        )

        result = check_drift(
            tmp_path, "invoice.j2.typ", fp, pdf,
            contract_valid=False,
        )
        contract_findings = [f for f in result.findings if f.check_name == "contract_status_change"]
        assert len(contract_findings) == 1
        assert contract_findings[0].severity == "error"

    def test_drift_result_serialization(self, tmp_path):
        data = _load_data()
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        pdf = _render_invoice(data)
        save_baseline(tmp_path, "invoice.j2.typ", fp, pdf)

        result = check_drift(tmp_path, "invoice.j2.typ", fp, pdf)
        d = result.to_dict()
        assert "passed" in d
        assert "findings" in d
        assert "checks_run" in d


class TestEmbeddedFontDrift:
    def test_font_extraction_from_real_pdf(self):
        """Rendered invoice contains Inter font names."""
        pdf = _render_invoice()
        fonts = _extract_embedded_fonts(pdf)
        assert fonts is not None
        # At least one Inter variant should be embedded
        assert any("Inter" in f for f in fonts)

    def test_embedded_fonts_in_baseline_json(self, tmp_path):
        """save_baseline() stores embedded_fonts in JSON."""
        data = _load_data()
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        pdf = _render_invoice(data)
        save_baseline(tmp_path, "invoice.j2.typ", fp, pdf)

        raw = json.loads((tmp_path / "invoice.j2.typ" / "latest.json").read_text())
        assert "embedded_fonts" in raw
        assert isinstance(raw["embedded_fonts"], list)
        assert len(raw["embedded_fonts"]) > 0

    def test_schema_version_bumped(self, tmp_path):
        data = _load_data()
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        pdf = _render_invoice(data)
        save_baseline(tmp_path, "invoice.j2.typ", fp, pdf)

        raw = json.loads((tmp_path / "invoice.j2.typ" / "latest.json").read_text())
        assert raw["schema_version"] == 2

    def test_font_drift_detected(self, tmp_path):
        """Font set change produces a warning finding."""
        data = _load_data()
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        pdf = _render_invoice(data)
        save_baseline(tmp_path, "invoice.j2.typ", fp, pdf)

        # Manipulate baseline to have different fonts
        raw = json.loads((tmp_path / "invoice.j2.typ" / "latest.json").read_text())
        raw["embedded_fonts"] = ["Libertinus-Regular", "Libertinus-Bold"]
        (tmp_path / "invoice.j2.typ" / "latest.json").write_text(
            json.dumps(raw, indent=2)
        )

        result = check_drift(tmp_path, "invoice.j2.typ", fp, pdf)
        assert result is not None
        font_findings = [
            f for f in result.findings if f.check_name == "embedded_fonts_changed"
        ]
        assert len(font_findings) == 1
        assert font_findings[0].severity == "warning"
        assert "removed" in font_findings[0].message
        assert "added" in font_findings[0].message
        assert font_findings[0].deterministic is True

    def test_font_drift_none_baseline_skips(self, tmp_path):
        """Old baseline without embedded_fonts → no font findings."""
        data = _load_data()
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        pdf = _render_invoice(data)
        save_baseline(tmp_path, "invoice.j2.typ", fp, pdf)

        # Simulate old v1 baseline by removing embedded_fonts
        raw = json.loads((tmp_path / "invoice.j2.typ" / "latest.json").read_text())
        del raw["embedded_fonts"]
        raw["schema_version"] = 1
        (tmp_path / "invoice.j2.typ" / "latest.json").write_text(
            json.dumps(raw, indent=2)
        )

        result = check_drift(tmp_path, "invoice.j2.typ", fp, pdf)
        assert result is not None
        font_findings = [
            f for f in result.findings if f.check_name == "embedded_fonts_changed"
        ]
        assert len(font_findings) == 0

    def test_no_font_drift_same_render(self, tmp_path):
        """Same render → no font drift."""
        data = _load_data()
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        pdf = _render_invoice(data)
        save_baseline(tmp_path, "invoice.j2.typ", fp, pdf)

        result = check_drift(tmp_path, "invoice.j2.typ", fp, pdf)
        font_findings = [
            f for f in result.findings if f.check_name == "embedded_fonts_changed"
        ]
        assert len(font_findings) == 0

    def test_font_extraction_empty_pdf(self):
        """Non-PDF bytes return None gracefully."""
        assert _extract_embedded_fonts(b"not a pdf") is None
        assert _extract_embedded_fonts(b"") is None
