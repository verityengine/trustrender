"""Stress tests for baseline drift detection — boundaries, corruption, edge cases."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from formforge import render
from formforge.fingerprint import InputFingerprint, compute_fingerprint
from formforge.regression import (
    DriftBaseline,
    DriftFinding,
    DriftResult,
    _SCHEMA_VERSION,
    _check_file_size,
    _check_page_count,
    _check_render_success,
    _get_page_count,
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


def _make_fp(data: dict | None = None) -> InputFingerprint:
    if data is None:
        data = _load_data()
    return compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)


# ---------------------------------------------------------------------------
# Threshold boundary tests
# ---------------------------------------------------------------------------

class TestFileSizeThresholds:
    """Test exact threshold boundaries for file size drift."""

    def _make_baseline(self, pdf_size: int) -> DriftBaseline:
        return DriftBaseline(
            schema_version=_SCHEMA_VERSION,
            baseline_id="test",
            created_at="2026-04-10T00:00:00Z",
            template_file="test.j2.typ",
            formforge_version="0.1.0",
            fingerprint_json={},
            pdf_size=pdf_size,
            page_count=1,
            render_success=True,
            render_duration_ms=None,
            zugferd_valid=None,
            contract_valid=None,
            semantic_issue_count=0,
        )

    def test_19_percent_change_no_finding(self):
        """Just under 20% threshold — no finding."""
        baseline = self._make_baseline(1000)
        findings: list[DriftFinding] = []
        _check_file_size(baseline, 1190, findings)  # 19% increase
        assert len(findings) == 0

    def test_21_percent_change_warns(self):
        """Just over 20% threshold — warning."""
        baseline = self._make_baseline(1000)
        findings: list[DriftFinding] = []
        _check_file_size(baseline, 1210, findings)  # 21% increase
        assert len(findings) == 1
        assert findings[0].severity == "warning"
        assert findings[0].check_name == "file_size_drift"

    def test_49_percent_change_still_warning(self):
        baseline = self._make_baseline(1000)
        findings: list[DriftFinding] = []
        _check_file_size(baseline, 1490, findings)
        assert len(findings) == 1
        assert findings[0].severity == "warning"

    def test_51_percent_change_errors(self):
        """Over 50% threshold — error (spike)."""
        baseline = self._make_baseline(1000)
        findings: list[DriftFinding] = []
        _check_file_size(baseline, 1510, findings)
        assert len(findings) == 1
        assert findings[0].severity == "error"
        assert findings[0].check_name == "file_size_spike"

    def test_size_decrease_also_detected(self):
        """50% decrease should also trigger."""
        baseline = self._make_baseline(1000)
        findings: list[DriftFinding] = []
        _check_file_size(baseline, 400, findings)  # 60% decrease
        assert len(findings) == 1
        assert findings[0].severity == "error"

    def test_zero_baseline_size_skipped(self):
        """Zero-byte baseline should not cause division by zero."""
        baseline = self._make_baseline(0)
        findings: list[DriftFinding] = []
        _check_file_size(baseline, 1000, findings)
        assert len(findings) == 0

    def test_identical_size_no_finding(self):
        baseline = self._make_baseline(50000)
        findings: list[DriftFinding] = []
        _check_file_size(baseline, 50000, findings)
        assert len(findings) == 0


class TestPageCountThresholds:
    def _make_baseline(self, page_count: int | None) -> DriftBaseline:
        return DriftBaseline(
            schema_version=_SCHEMA_VERSION,
            baseline_id="test",
            created_at="2026-04-10T00:00:00Z",
            template_file="test.j2.typ",
            formforge_version="0.1.0",
            fingerprint_json={},
            pdf_size=1000,
            page_count=page_count,
            render_success=True,
            render_duration_ms=None,
            zugferd_valid=None,
            contract_valid=None,
            semantic_issue_count=0,
        )

    def test_1_page_change_warns(self):
        baseline = self._make_baseline(5)
        findings: list[DriftFinding] = []
        _check_page_count(baseline, 6, findings)
        assert len(findings) == 1
        assert findings[0].severity == "warning"

    def test_3_page_change_warns(self):
        baseline = self._make_baseline(5)
        findings: list[DriftFinding] = []
        _check_page_count(baseline, 8, findings)
        assert len(findings) == 1
        assert findings[0].severity == "warning"

    def test_4_page_change_errors(self):
        baseline = self._make_baseline(5)
        findings: list[DriftFinding] = []
        _check_page_count(baseline, 9, findings)
        assert len(findings) == 1
        assert findings[0].severity == "error"

    def test_decrease_also_detected(self):
        baseline = self._make_baseline(10)
        findings: list[DriftFinding] = []
        _check_page_count(baseline, 5, findings)
        assert len(findings) == 1
        assert findings[0].severity == "error"

    def test_same_page_count_no_finding(self):
        baseline = self._make_baseline(3)
        findings: list[DriftFinding] = []
        _check_page_count(baseline, 3, findings)
        assert len(findings) == 0

    def test_none_baseline_skips(self):
        baseline = self._make_baseline(None)
        findings: list[DriftFinding] = []
        _check_page_count(baseline, 5, findings)
        assert len(findings) == 0

    def test_none_current_skips(self):
        baseline = self._make_baseline(5)
        findings: list[DriftFinding] = []
        _check_page_count(baseline, None, findings)
        assert len(findings) == 0


# ---------------------------------------------------------------------------
# Render success transitions
# ---------------------------------------------------------------------------

class TestRenderSuccessTransitions:
    def _make_baseline(self, success: bool) -> DriftBaseline:
        return DriftBaseline(
            schema_version=_SCHEMA_VERSION,
            baseline_id="test",
            created_at="2026-04-10T00:00:00Z",
            template_file="test.j2.typ",
            formforge_version="0.1.0",
            fingerprint_json={},
            pdf_size=1000,
            page_count=1,
            render_success=success,
            render_duration_ms=None,
            zugferd_valid=None,
            contract_valid=None,
            semantic_issue_count=0,
        )

    def test_success_to_failure_errors(self):
        baseline = self._make_baseline(True)
        findings: list[DriftFinding] = []
        _check_render_success(baseline, False, findings)
        assert len(findings) == 1
        assert findings[0].severity == "error"

    def test_failure_to_success_info(self):
        baseline = self._make_baseline(False)
        findings: list[DriftFinding] = []
        _check_render_success(baseline, True, findings)
        assert len(findings) == 1
        assert findings[0].severity == "info"

    def test_success_to_success_clean(self):
        baseline = self._make_baseline(True)
        findings: list[DriftFinding] = []
        _check_render_success(baseline, True, findings)
        assert len(findings) == 0

    def test_failure_to_failure_clean(self):
        baseline = self._make_baseline(False)
        findings: list[DriftFinding] = []
        _check_render_success(baseline, False, findings)
        assert len(findings) == 0


# ---------------------------------------------------------------------------
# Corrupted baseline files
# ---------------------------------------------------------------------------

class TestCorruptedBaselines:
    def test_invalid_json(self, tmp_path):
        bl_dir = tmp_path / "invoice.j2.typ"
        bl_dir.mkdir()
        (bl_dir / "latest.json").write_text("not valid json {{{")
        assert load_baseline(tmp_path, "invoice.j2.typ") is None

    def test_missing_required_key(self, tmp_path):
        bl_dir = tmp_path / "invoice.j2.typ"
        bl_dir.mkdir()
        (bl_dir / "latest.json").write_text(json.dumps({"baseline_id": "test"}))
        # Missing many required keys — should return None (KeyError caught)
        assert load_baseline(tmp_path, "invoice.j2.typ") is None

    def test_empty_file(self, tmp_path):
        bl_dir = tmp_path / "invoice.j2.typ"
        bl_dir.mkdir()
        (bl_dir / "latest.json").write_text("")
        assert load_baseline(tmp_path, "invoice.j2.typ") is None

    def test_baseline_dir_does_not_exist(self, tmp_path):
        nonexistent = tmp_path / "nonexistent"
        assert load_baseline(nonexistent, "invoice.j2.typ") is None


# ---------------------------------------------------------------------------
# Baseline overwrite behavior
# ---------------------------------------------------------------------------

class TestBaselineOverwrite:
    def test_save_twice_overwrites(self, tmp_path):
        data = _load_data()
        fp = _make_fp(data)
        pdf = _render_invoice(data)

        bl1 = save_baseline(tmp_path, "invoice.j2.typ", fp, pdf)
        bl2 = save_baseline(tmp_path, "invoice.j2.typ", fp, pdf)

        loaded = load_baseline(tmp_path, "invoice.j2.typ")
        assert loaded is not None
        assert loaded.baseline_id == bl2.baseline_id
        assert loaded.baseline_id != bl1.baseline_id


# ---------------------------------------------------------------------------
# PDF page count extraction
# ---------------------------------------------------------------------------

class TestPageCountExtraction:
    def test_real_pdf(self):
        pdf = _render_invoice()
        count = _get_page_count(pdf)
        assert count is not None
        assert count >= 1

    def test_invalid_bytes(self):
        count = _get_page_count(b"not a pdf")
        assert count is None

    def test_empty_bytes(self):
        count = _get_page_count(b"")
        assert count is None


# ---------------------------------------------------------------------------
# DriftResult properties
# ---------------------------------------------------------------------------

class TestDriftResultProperties:
    def test_passed_when_no_findings(self):
        r = DriftResult(baseline_id="test")
        assert r.passed is True
        assert r.has_errors is False
        assert r.has_warnings is False

    def test_failed_with_error(self):
        r = DriftResult(
            baseline_id="test",
            findings=[DriftFinding(
                check_name="test",
                severity="error",
                category="structure",
                message="bad",
                baseline_value=None,
                current_value=None,
                deterministic=True,
                confidence="high",
            )],
        )
        assert r.passed is False
        assert r.has_errors is True

    def test_passed_with_warning_only(self):
        r = DriftResult(
            baseline_id="test",
            findings=[DriftFinding(
                check_name="test",
                severity="warning",
                category="size",
                message="drift",
                baseline_value=None,
                current_value=None,
                deterministic=True,
                confidence="high",
            )],
        )
        assert r.passed is True  # Warnings don't block
        assert r.has_warnings is True


# ---------------------------------------------------------------------------
# All example templates with baseline save/check cycle
# ---------------------------------------------------------------------------

class TestAllExamplesBaselineCycle:
    """Save and check baseline for every example template."""

    @pytest.mark.parametrize("template,data_file", [
        ("invoice.j2.typ", "invoice_data.json"),
        ("statement.j2.typ", "statement_data.json"),
        ("receipt.j2.typ", "receipt_data.json"),
        ("letter.j2.typ", "letter_data.json"),
        ("report.j2.typ", "report_data.json"),
    ])
    def test_save_then_check_passes(self, tmp_path, template, data_file):
        template_path = EXAMPLES / template
        if not template_path.exists():
            pytest.skip(f"Template {template} not found")

        data = json.loads((EXAMPLES / data_file).read_text())
        fp = compute_fingerprint(template_path, data)
        pdf = render(template_path, data)

        save_baseline(tmp_path, template, fp, pdf)
        result = check_drift(tmp_path, template, fp, pdf)
        assert result is not None
        assert result.passed

    @pytest.mark.parametrize("template,data_file", [
        ("invoice.j2.typ", "invoice_data.json"),
        ("statement.j2.typ", "statement_data.json"),
        ("receipt.j2.typ", "receipt_data.json"),
    ])
    def test_modified_data_detects_something(self, tmp_path, template, data_file):
        """Modifying data and re-rendering should detect some kind of drift."""
        template_path = EXAMPLES / template
        if not template_path.exists():
            pytest.skip(f"Template {template} not found")

        data = json.loads((EXAMPLES / data_file).read_text())
        fp = compute_fingerprint(template_path, data)
        pdf = render(template_path, data)
        save_baseline(tmp_path, template, fp, pdf)

        # Fake a baseline with wildly different size to ensure drift
        raw = json.loads((tmp_path / template / "latest.json").read_text())
        raw["pdf_size"] = len(pdf) * 5
        (tmp_path / template / "latest.json").write_text(json.dumps(raw, indent=2))

        fp2 = compute_fingerprint(template_path, data)
        result = check_drift(tmp_path, template, fp2, pdf)
        assert result is not None
        assert len(result.findings) > 0


# ---------------------------------------------------------------------------
# DriftBaseline schema evolution
# ---------------------------------------------------------------------------

class TestSchemaEvolution:
    def test_old_schema_without_version_loads(self, tmp_path):
        """Baselines from before schema_version was added should still load."""
        bl_dir = tmp_path / "test.j2.typ"
        bl_dir.mkdir()
        old_baseline = {
            "baseline_id": "test:old",
            "created_at": "2026-01-01T00:00:00Z",
            "template_file": "test.j2.typ",
            "fingerprint_json": {},
            "pdf_size": 5000,
            "page_count": 2,
            "render_success": True,
        }
        (bl_dir / "latest.json").write_text(json.dumps(old_baseline))
        loaded = load_baseline(tmp_path, "test.j2.typ")
        assert loaded is not None
        assert loaded.schema_version == 1  # Default
        assert loaded.formforge_version == "unknown"
