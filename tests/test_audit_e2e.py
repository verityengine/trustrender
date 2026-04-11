"""End-to-end stress tests for the audit() function and CLI integration."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from formforge import AuditResult, FormforgeError, audit, render
from formforge.fingerprint import InputFingerprint, compare
from formforge.regression import DriftResult, load_baseline, save_baseline
from formforge.semantic import INVOICE_HINTS, SemanticHints

EXAMPLES = Path(__file__).parent.parent / "examples"


def _load_data(name: str = "invoice_data.json") -> dict:
    return json.loads((EXAMPLES / name).read_text())


# ---------------------------------------------------------------------------
# Basic audit() tests
# ---------------------------------------------------------------------------

class TestAuditBasic:
    def test_audit_returns_pdf(self):
        result = audit(EXAMPLES / "invoice.j2.typ", _load_data())
        assert isinstance(result, AuditResult)
        assert len(result.pdf_bytes) > 0
        assert result.pdf_bytes[:5] == b"%PDF-"

    def test_audit_returns_fingerprint(self):
        result = audit(EXAMPLES / "invoice.j2.typ", _load_data())
        fp = result.fingerprint
        assert fp.fingerprint.startswith("sha256:")
        assert fp.data_hash.startswith("sha256:")

    def test_audit_no_baseline_no_drift(self):
        result = audit(EXAMPLES / "invoice.j2.typ", _load_data())
        assert result.change_set is None
        assert result.drift_result is None

    def test_audit_no_hints_no_semantic(self):
        result = audit(EXAMPLES / "invoice.j2.typ", _load_data())
        assert result.semantic_report is None

    def test_audit_with_semantic(self):
        result = audit(
            EXAMPLES / "invoice.j2.typ",
            _load_data(),
            semantic_hints=INVOICE_HINTS,
        )
        assert result.semantic_report is not None
        assert len(result.semantic_report.checks_run) == 5

    def test_audit_matches_render(self):
        """audit() should produce the same PDF bytes as render()."""
        data = _load_data()
        pdf_render = render(EXAMPLES / "invoice.j2.typ", data)
        result = audit(EXAMPLES / "invoice.j2.typ", data)
        # PDFs may not be byte-identical due to timestamps, but should be same size
        assert abs(len(result.pdf_bytes) - len(pdf_render)) < 100

    def test_audit_with_output_file(self, tmp_path):
        out = tmp_path / "test.pdf"
        result = audit(
            EXAMPLES / "invoice.j2.typ",
            _load_data(),
            output=out,
        )
        assert out.exists()
        assert out.read_bytes() == result.pdf_bytes


# ---------------------------------------------------------------------------
# Baseline save/check cycle via audit()
# ---------------------------------------------------------------------------

class TestAuditBaselineCycle:
    def test_save_then_check_passes(self, tmp_path):
        data = _load_data()
        # Save baseline
        result1 = audit(
            EXAMPLES / "invoice.j2.typ", data,
            baseline_dir=tmp_path,
            save_baseline=True,
        )
        assert result1.drift_result is None  # No prior baseline

        # Check against baseline (same data)
        result2 = audit(
            EXAMPLES / "invoice.j2.typ", data,
            baseline_dir=tmp_path,
        )
        assert result2.drift_result is not None
        assert result2.drift_result.passed
        assert result2.change_set is not None

    def test_modified_data_detects_changes(self, tmp_path):
        data = _load_data()
        audit(
            EXAMPLES / "invoice.j2.typ", data,
            baseline_dir=tmp_path,
            save_baseline=True,
        )

        # Modify data
        data2 = _load_data()
        data2["invoice_number"] = "INV-CHANGED-999"
        result = audit(
            EXAMPLES / "invoice.j2.typ", data2,
            baseline_dir=tmp_path,
        )
        assert result.change_set is not None
        assert result.change_set.has_changes
        assert "data" in result.change_set.change_categories

    def test_baseline_dir_without_save(self, tmp_path):
        """Providing baseline_dir without saving first returns no drift."""
        result = audit(
            EXAMPLES / "invoice.j2.typ", _load_data(),
            baseline_dir=tmp_path,
        )
        # No baseline saved yet, so drift_result is None
        assert result.drift_result is None

    def test_overwrite_baseline(self, tmp_path):
        data = _load_data()
        # Save initial baseline
        audit(EXAMPLES / "invoice.j2.typ", data,
              baseline_dir=tmp_path, save_baseline=True)

        # Save again (overwrite)
        audit(EXAMPLES / "invoice.j2.typ", data,
              baseline_dir=tmp_path, save_baseline=True)

        # Should still load
        bl = load_baseline(tmp_path, "invoice.j2.typ")
        assert bl is not None


# ---------------------------------------------------------------------------
# Audit with all options enabled
# ---------------------------------------------------------------------------

class TestAuditAllOptions:
    def test_validate_and_audit(self):
        result = audit(
            EXAMPLES / "invoice.j2.typ",
            _load_data(),
            validate=True,
            semantic_hints=INVOICE_HINTS,
        )
        assert result.fingerprint.validate_enabled is True
        assert result.semantic_report is not None

    def test_provenance_and_audit(self):
        result = audit(
            EXAMPLES / "invoice.j2.typ",
            _load_data(),
            provenance=True,
        )
        assert result.fingerprint.provenance_enabled is True
        # PDF should have provenance metadata
        from formforge.provenance import extract_provenance
        prov = extract_provenance(result.pdf_bytes)
        assert prov is not None

    def test_full_stack(self, tmp_path):
        """All options enabled simultaneously."""
        data = _load_data()
        result = audit(
            EXAMPLES / "invoice.j2.typ", data,
            validate=True,
            provenance=True,
            baseline_dir=tmp_path,
            save_baseline=True,
            semantic_hints=INVOICE_HINTS,
        )
        assert len(result.pdf_bytes) > 0
        assert result.fingerprint is not None
        assert result.semantic_report is not None
        # Drift is None because we just saved (no prior baseline)
        assert result.drift_result is None

        # Now check against saved baseline
        result2 = audit(
            EXAMPLES / "invoice.j2.typ", data,
            validate=True,
            provenance=True,
            baseline_dir=tmp_path,
            semantic_hints=INVOICE_HINTS,
        )
        assert result2.drift_result is not None
        assert result2.drift_result.passed


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------

class TestAuditErrors:
    def test_missing_template(self):
        with pytest.raises(FormforgeError) as exc_info:
            audit("nonexistent.j2.typ", {})
        assert exc_info.value.code.value == "TEMPLATE_NOT_FOUND"

    def test_invalid_data_type(self):
        with pytest.raises(FormforgeError):
            audit(EXAMPLES / "invoice.j2.typ", 42)  # type: ignore

    def test_bad_json_string(self):
        with pytest.raises(FormforgeError):
            audit(EXAMPLES / "invoice.j2.typ", "not json {{{")

    def test_invalid_zugferd_profile(self):
        with pytest.raises(FormforgeError) as exc_info:
            audit(EXAMPLES / "invoice.j2.typ", _load_data(), zugferd="invalid")
        assert exc_info.value.code.value == "INVALID_DATA"


# ---------------------------------------------------------------------------
# All example templates via audit()
# ---------------------------------------------------------------------------

class TestAuditAllExamples:
    @pytest.mark.parametrize("template,data_file", [
        ("invoice.j2.typ", "invoice_data.json"),
        ("statement.j2.typ", "statement_data.json"),
        ("receipt.j2.typ", "receipt_data.json"),
        ("letter.j2.typ", "letter_data.json"),
        ("report.j2.typ", "report_data.json"),
    ])
    def test_audit_every_example(self, template, data_file):
        template_path = EXAMPLES / template
        if not template_path.exists():
            pytest.skip(f"Template {template} not found")
        data = json.loads((EXAMPLES / data_file).read_text())
        result = audit(template_path, data)
        assert len(result.pdf_bytes) > 0
        assert result.fingerprint.fingerprint.startswith("sha256:")

    @pytest.mark.parametrize("template,data_file", [
        ("invoice.j2.typ", "invoice_data.json"),
        ("statement.j2.typ", "statement_data.json"),
        ("receipt.j2.typ", "receipt_data.json"),
    ])
    def test_full_cycle_every_template(self, tmp_path, template, data_file):
        """Save baseline, then check — should pass for same data."""
        template_path = EXAMPLES / template
        if not template_path.exists():
            pytest.skip(f"Template {template} not found")
        data = json.loads((EXAMPLES / data_file).read_text())

        audit(template_path, data, baseline_dir=tmp_path, save_baseline=True)
        result = audit(template_path, data, baseline_dir=tmp_path)
        assert result.drift_result is not None
        assert result.drift_result.passed


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------

class TestCLI:
    def _run_cli(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-m", "formforge.cli", *args],
            capture_output=True,
            text=True,
            timeout=30,
        )

    def test_audit_basic(self):
        result = self._run_cli(
            "audit",
            str(EXAMPLES / "invoice.j2.typ"),
            str(EXAMPLES / "invoice_data.json"),
        )
        assert result.returncode == 0
        assert "Fingerprint:" in result.stdout

    def test_audit_with_semantic(self):
        result = self._run_cli(
            "audit",
            str(EXAMPLES / "invoice.j2.typ"),
            str(EXAMPLES / "invoice_data.json"),
            "--semantic",
        )
        assert result.returncode == 0
        assert "Semantic:" in result.stdout

    def test_audit_json_output(self):
        result = self._run_cli(
            "audit",
            str(EXAMPLES / "invoice.j2.typ"),
            str(EXAMPLES / "invoice_data.json"),
            "--json",
        )
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "fingerprint" in data
        assert data["fingerprint"]["fingerprint"].startswith("sha256:")

    def test_audit_missing_template(self):
        result = self._run_cli(
            "audit", "nonexistent.j2.typ",
            str(EXAMPLES / "invoice_data.json"),
        )
        assert result.returncode != 0

    def test_audit_missing_data(self):
        result = self._run_cli(
            "audit",
            str(EXAMPLES / "invoice.j2.typ"),
            "nonexistent.json",
        )
        assert result.returncode != 0

    def test_baseline_save_and_check(self, tmp_path):
        bl_dir = str(tmp_path)

        # Save
        result = self._run_cli(
            "baseline", "save",
            str(EXAMPLES / "invoice.j2.typ"),
            str(EXAMPLES / "invoice_data.json"),
            "--baseline-dir", bl_dir,
        )
        assert result.returncode == 0
        assert "Baseline saved" in result.stdout

        # Check
        result = self._run_cli(
            "baseline", "check",
            str(EXAMPLES / "invoice.j2.typ"),
            str(EXAMPLES / "invoice_data.json"),
            "--baseline-dir", bl_dir,
        )
        assert result.returncode == 0
        assert "PASS" in result.stdout

    def test_baseline_check_no_baseline(self, tmp_path):
        result = self._run_cli(
            "baseline", "check",
            str(EXAMPLES / "invoice.j2.typ"),
            str(EXAMPLES / "invoice_data.json"),
            "--baseline-dir", str(tmp_path),
        )
        assert result.returncode == 1
        assert "No baseline found" in result.stdout

    def test_preflight_with_semantic(self):
        result = self._run_cli(
            "preflight",
            str(EXAMPLES / "invoice.j2.typ"),
            str(EXAMPLES / "invoice_data.json"),
            "--semantic",
        )
        assert result.returncode == 0

    def test_audit_with_output(self, tmp_path):
        out = str(tmp_path / "test.pdf")
        result = self._run_cli(
            "audit",
            str(EXAMPLES / "invoice.j2.typ"),
            str(EXAMPLES / "invoice_data.json"),
            "-o", out,
        )
        assert result.returncode == 0
        assert Path(out).exists()

    def test_audit_with_baseline_cycle(self, tmp_path):
        bl_dir = str(tmp_path)

        # Audit + save baseline
        result = self._run_cli(
            "audit",
            str(EXAMPLES / "invoice.j2.typ"),
            str(EXAMPLES / "invoice_data.json"),
            "--baseline-dir", bl_dir,
            "--save-baseline",
        )
        assert result.returncode == 0
        assert "Baseline saved" in result.stdout

        # Audit + check against baseline
        result = self._run_cli(
            "audit",
            str(EXAMPLES / "invoice.j2.typ"),
            str(EXAMPLES / "invoice_data.json"),
            "--baseline-dir", bl_dir,
        )
        assert result.returncode == 0
        assert "No input changes detected" in result.stdout
        assert "PASS" in result.stdout
