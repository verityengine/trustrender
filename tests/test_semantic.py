"""Tests for semantic payload validation."""

from __future__ import annotations

import pytest

from formforge.semantic import (
    INVOICE_HINTS,
    SemanticHints,
    SemanticIssue,
    SemanticReport,
    validate_semantics,
)


class TestArithmeticConsistency:
    def test_correct_sum_passes(self):
        data = {
            "items": [
                {"line_total": 100.0},
                {"line_total": 200.0},
                {"line_total": 300.0},
            ],
            "subtotal": 600.0,
        }
        hints = SemanticHints(
            line_items_path="items",
            line_total_field="line_total",
            subtotal_path="subtotal",
        )
        report = validate_semantics(data, hints=hints)
        arith = [i for i in report.issues if i.category == "arithmetic"]
        assert len(arith) == 0

    def test_wrong_sum_warns(self):
        data = {
            "items": [
                {"line_total": 100.0},
                {"line_total": 200.0},
            ],
            "subtotal": 500.0,  # Wrong: should be 300
        }
        hints = SemanticHints(
            line_items_path="items",
            line_total_field="line_total",
            subtotal_path="subtotal",
        )
        report = validate_semantics(data, hints=hints)
        arith = [i for i in report.issues if i.category == "arithmetic"]
        assert len(arith) == 1
        assert arith[0].severity == "warning"
        assert arith[0].deterministic is True

    def test_currency_string_parsing(self):
        """Line totals as formatted currency strings."""
        data = {
            "items": [
                {"line_total": "$1,500.00"},
                {"line_total": "$2,500.00"},
            ],
            "subtotal": "$4,000.00",
        }
        hints = SemanticHints(
            line_items_path="items",
            line_total_field="line_total",
            subtotal_path="subtotal",
        )
        report = validate_semantics(data, hints=hints)
        arith = [i for i in report.issues if i.category == "arithmetic"]
        assert len(arith) == 0

    def test_currency_mismatch_warns(self):
        data = {
            "items": [
                {"line_total": "$1,500.00"},
                {"line_total": "$2,500.00"},
            ],
            "subtotal": "$5,000.00",  # Wrong
        }
        hints = SemanticHints(
            line_items_path="items",
            line_total_field="line_total",
            subtotal_path="subtotal",
        )
        report = validate_semantics(data, hints=hints)
        arith = [i for i in report.issues if i.category == "arithmetic"]
        assert len(arith) == 1

    def test_float_tolerance(self):
        """Small floating-point differences should not trigger."""
        data = {
            "items": [
                {"line_total": 33.33},
                {"line_total": 33.33},
                {"line_total": 33.34},
            ],
            "subtotal": 100.00,
        }
        hints = SemanticHints(
            line_items_path="items",
            line_total_field="line_total",
            subtotal_path="subtotal",
        )
        report = validate_semantics(data, hints=hints)
        arith = [i for i in report.issues if i.category == "arithmetic"]
        assert len(arith) == 0

    def test_skips_when_no_hints(self):
        report = validate_semantics({"items": []}, hints=SemanticHints())
        assert not report.issues


class TestDateParseability:
    def test_valid_dates_pass(self):
        data = {
            "invoice_date": "2026-04-10",
            "due_date": "May 10, 2026",
        }
        hints = SemanticHints(date_fields=["invoice_date", "due_date"])
        report = validate_semantics(data, hints=hints)
        date_issues = [i for i in report.issues if i.category == "date_format"]
        assert len(date_issues) == 0

    def test_unparseable_date_warns(self):
        data = {"invoice_date": "not-a-date"}
        hints = SemanticHints(date_fields=["invoice_date"])
        report = validate_semantics(data, hints=hints)
        date_issues = [i for i in report.issues if i.category == "date_format"]
        assert len(date_issues) == 1
        assert date_issues[0].severity == "warning"

    def test_non_string_date_warns(self):
        data = {"invoice_date": 12345}
        hints = SemanticHints(date_fields=["invoice_date"])
        report = validate_semantics(data, hints=hints)
        date_issues = [i for i in report.issues if i.category == "date_format"]
        assert len(date_issues) == 1

    def test_missing_date_field_skipped(self):
        data = {}
        hints = SemanticHints(date_fields=["invoice_date"])
        report = validate_semantics(data, hints=hints)
        date_issues = [i for i in report.issues if i.category == "date_format"]
        assert len(date_issues) == 0  # Missing handled by contract, not semantic

    def test_multiple_date_formats(self):
        data = {
            "d1": "2026-04-10",
            "d2": "04/10/2026",
            "d3": "April 10, 2026",
            "d4": "Apr 10, 2026",
        }
        hints = SemanticHints(date_fields=["d1", "d2", "d3", "d4"])
        report = validate_semantics(data, hints=hints)
        assert len([i for i in report.issues if i.category == "date_format"]) == 0


class TestCompleteness:
    def test_nonempty_passes(self):
        data = {"invoice_number": "INV-001"}
        hints = SemanticHints(nonempty_fields=["invoice_number"])
        report = validate_semantics(data, hints=hints)
        comp = [i for i in report.issues if i.category == "completeness"]
        assert len(comp) == 0

    def test_empty_string_warns(self):
        data = {"invoice_number": ""}
        hints = SemanticHints(nonempty_fields=["invoice_number"])
        report = validate_semantics(data, hints=hints)
        comp = [i for i in report.issues if i.category == "completeness"]
        assert len(comp) == 1
        assert comp[0].severity == "warning"

    def test_none_warns(self):
        data = {"invoice_number": None}
        hints = SemanticHints(nonempty_fields=["invoice_number"])
        report = validate_semantics(data, hints=hints)
        comp = [i for i in report.issues if i.category == "completeness"]
        assert len(comp) == 1

    def test_missing_field_warns(self):
        data = {}
        hints = SemanticHints(nonempty_fields=["invoice_number"])
        report = validate_semantics(data, hints=hints)
        comp = [i for i in report.issues if i.category == "completeness"]
        assert len(comp) == 1

    def test_whitespace_only_warns(self):
        data = {"invoice_number": "   "}
        hints = SemanticHints(nonempty_fields=["invoice_number"])
        report = validate_semantics(data, hints=hints)
        comp = [i for i in report.issues if i.category == "completeness"]
        assert len(comp) == 1


class TestNumericCoercion:
    def test_numeric_passes(self):
        data = {"items": [{"quantity": 5, "unit_price": 10.50}]}
        hints = SemanticHints(
            numeric_fields=["items[].quantity", "items[].unit_price"],
        )
        report = validate_semantics(data, hints=hints)
        num = [i for i in report.issues if i.category == "numeric_coercion"]
        assert len(num) == 0

    def test_string_number_passes(self):
        data = {"items": [{"quantity": "5", "unit_price": "$10.50"}]}
        hints = SemanticHints(
            numeric_fields=["items[].quantity", "items[].unit_price"],
        )
        report = validate_semantics(data, hints=hints)
        num = [i for i in report.issues if i.category == "numeric_coercion"]
        assert len(num) == 0

    def test_non_numeric_warns(self):
        data = {"items": [{"quantity": "five"}]}
        hints = SemanticHints(numeric_fields=["items[].quantity"])
        report = validate_semantics(data, hints=hints)
        num = [i for i in report.issues if i.category == "numeric_coercion"]
        assert len(num) == 1
        assert num[0].path == "items[0].quantity"

    def test_scalar_numeric_field(self):
        data = {"total": "not-a-number"}
        hints = SemanticHints(numeric_fields=["total"])
        report = validate_semantics(data, hints=hints)
        num = [i for i in report.issues if i.category == "numeric_coercion"]
        assert len(num) == 1

    def test_multiple_items_checked(self):
        data = {
            "items": [
                {"quantity": 5},
                {"quantity": "bad"},
                {"quantity": 3},
            ],
        }
        hints = SemanticHints(numeric_fields=["items[].quantity"])
        report = validate_semantics(data, hints=hints)
        num = [i for i in report.issues if i.category == "numeric_coercion"]
        assert len(num) == 1
        assert num[0].path == "items[1].quantity"


class TestNoHints:
    def test_no_hints_no_checks(self):
        report = validate_semantics({"anything": "value"}, hints=None)
        assert len(report.issues) == 0
        assert len(report.checks_run) == 0

    def test_empty_hints_runs_checks(self):
        report = validate_semantics({"anything": "value"}, hints=SemanticHints())
        assert len(report.issues) == 0
        assert len(report.checks_run) == 4  # All 4 checks run, just nothing to find


class TestInvoiceHints:
    def test_invoice_hints_on_real_data(self):
        """INVOICE_HINTS should work on real invoice data without errors."""
        import json
        from pathlib import Path

        examples = Path(__file__).parent.parent / "examples"
        data = json.loads((examples / "invoice_data.json").read_text())
        report = validate_semantics(data, hints=INVOICE_HINTS)
        # Real invoice data has string-formatted currency,
        # arithmetic check may or may not match depending on format.
        # No errors expected (warnings are OK).
        assert not report.has_errors


class TestReportSerialization:
    def test_to_dict(self):
        report = SemanticReport(
            issues=[
                SemanticIssue(
                    category="arithmetic",
                    severity="warning",
                    path="subtotal",
                    message="Sum mismatch",
                    expected="300.00",
                    actual="500.00",
                    deterministic=True,
                ),
            ],
            checks_run=["arithmetic_consistency"],
        )
        d = report.to_dict()
        assert len(d["issues"]) == 1
        assert d["issues"][0]["deterministic"] is True
