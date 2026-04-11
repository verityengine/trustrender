"""Stress tests for semantic validation — edge cases, adversarial inputs, boundaries."""

from __future__ import annotations

import pytest

from formforge.semantic import (
    INVOICE_HINTS,
    SemanticHints,
    SemanticReport,
    _resolve_path,
    _try_parse_date,
    _try_parse_number,
    validate_semantics,
)


# ---------------------------------------------------------------------------
# Number parsing edge cases
# ---------------------------------------------------------------------------

class TestNumberParsing:
    def test_integer(self):
        assert _try_parse_number(5) == 5.0

    def test_float(self):
        assert _try_parse_number(3.14) == 3.14

    def test_string_int(self):
        assert _try_parse_number("42") == 42.0

    def test_string_float(self):
        assert _try_parse_number("3.14") == 3.14

    def test_dollar_sign(self):
        assert _try_parse_number("$1,234.56") == 1234.56

    def test_euro_sign(self):
        assert _try_parse_number("€1.234,56") is not None or _try_parse_number("€1234.56") == 1234.56

    def test_negative_dollar(self):
        assert _try_parse_number("-$500.00") == -500.0

    def test_parens_negative(self):
        """Accounting notation: (500.00) means -500."""
        assert _try_parse_number("(500.00)") == -500.0

    def test_empty_string(self):
        assert _try_parse_number("") is None

    def test_pure_text(self):
        assert _try_parse_number("hello") is None

    def test_none(self):
        assert _try_parse_number(None) is None

    def test_list(self):
        assert _try_parse_number([1, 2, 3]) is None

    def test_dict(self):
        assert _try_parse_number({"a": 1}) is None

    def test_bool_true(self):
        # bool is subclass of int in Python
        result = _try_parse_number(True)
        assert result == 1.0

    def test_zero(self):
        assert _try_parse_number(0) == 0.0
        assert _try_parse_number("0") == 0.0
        assert _try_parse_number("$0.00") == 0.0

    def test_very_large_number(self):
        assert _try_parse_number("999999999.99") == 999999999.99

    def test_whitespace(self):
        # After stripping currency and whitespace
        assert _try_parse_number(" 42 ") == 42.0

    def test_comma_thousands(self):
        assert _try_parse_number("1,000,000") == 1000000.0

    def test_pound_sign(self):
        assert _try_parse_number("£500.00") == 500.0

    def test_yen_sign(self):
        assert _try_parse_number("¥10000") == 10000.0


# ---------------------------------------------------------------------------
# Date parsing edge cases
# ---------------------------------------------------------------------------

class TestDateParsing:
    def test_iso_format(self):
        assert _try_parse_date("2026-04-10") is True

    def test_us_format(self):
        assert _try_parse_date("04/10/2026") is True

    def test_european_format(self):
        assert _try_parse_date("10.04.2026") is True

    def test_long_month(self):
        assert _try_parse_date("April 10, 2026") is True

    def test_short_month(self):
        assert _try_parse_date("Apr 10, 2026") is True

    def test_iso_with_time(self):
        assert _try_parse_date("2026-04-10T14:30:00") is True

    def test_garbage(self):
        assert _try_parse_date("not-a-date") is False

    def test_empty(self):
        assert _try_parse_date("") is False

    def test_just_year(self):
        assert _try_parse_date("2026") is False

    def test_numeric_string(self):
        assert _try_parse_date("12345") is False

    def test_partial_date(self):
        assert _try_parse_date("Apr 10") is True  # Short month format


# ---------------------------------------------------------------------------
# Path resolution edge cases
# ---------------------------------------------------------------------------

class TestPathResolution:
    def test_simple_key(self):
        assert _resolve_path({"a": 1}, "a") == 1

    def test_nested(self):
        assert _resolve_path({"a": {"b": {"c": 3}}}, "a.b.c") == 3

    def test_missing_key(self):
        assert _resolve_path({"a": 1}, "b") is None

    def test_missing_nested_key(self):
        assert _resolve_path({"a": {"b": 1}}, "a.c") is None

    def test_non_dict_intermediate(self):
        assert _resolve_path({"a": "string"}, "a.b") is None

    def test_empty_dict(self):
        assert _resolve_path({}, "a") is None

    def test_none_value(self):
        assert _resolve_path({"a": None}, "a") is None

    def test_list_value(self):
        """Path resolution doesn't handle list indexing — returns the list."""
        assert _resolve_path({"a": [1, 2, 3]}, "a") == [1, 2, 3]


# ---------------------------------------------------------------------------
# Arithmetic edge cases
# ---------------------------------------------------------------------------

class TestArithmeticEdgeCases:
    def test_empty_items_list(self):
        data = {"items": [], "subtotal": 0}
        hints = SemanticHints(
            line_items_path="items",
            line_total_field="line_total",
            subtotal_path="subtotal",
        )
        report = validate_semantics(data, hints=hints)
        arith = [i for i in report.issues if i.category == "arithmetic"]
        assert len(arith) == 0  # No items = no check

    def test_non_list_items(self):
        data = {"items": "not a list", "subtotal": 0}
        hints = SemanticHints(
            line_items_path="items",
            line_total_field="line_total",
            subtotal_path="subtotal",
        )
        report = validate_semantics(data, hints=hints)
        arith = [i for i in report.issues if i.category == "arithmetic"]
        assert len(arith) == 0  # Gracefully skips

    def test_missing_items_path(self):
        data = {"subtotal": 100}
        hints = SemanticHints(
            line_items_path="items",
            line_total_field="line_total",
            subtotal_path="subtotal",
        )
        report = validate_semantics(data, hints=hints)
        arith = [i for i in report.issues if i.category == "arithmetic"]
        assert len(arith) == 0

    def test_non_numeric_subtotal(self):
        data = {"items": [{"line_total": 100}], "subtotal": "not a number"}
        hints = SemanticHints(
            line_items_path="items",
            line_total_field="line_total",
            subtotal_path="subtotal",
        )
        report = validate_semantics(data, hints=hints)
        arith = [i for i in report.issues if i.category == "arithmetic"]
        assert len(arith) == 0  # Can't check without numeric subtotal

    def test_all_non_numeric_items(self):
        data = {
            "items": [{"line_total": "abc"}, {"line_total": "def"}],
            "subtotal": 100,
        }
        hints = SemanticHints(
            line_items_path="items",
            line_total_field="line_total",
            subtotal_path="subtotal",
        )
        report = validate_semantics(data, hints=hints)
        arith = [i for i in report.issues if i.category == "arithmetic"]
        assert len(arith) == 0  # No parseable items = skip

    def test_mixed_numeric_and_non_numeric(self):
        data = {
            "items": [
                {"line_total": 100},
                {"line_total": "not a number"},
                {"line_total": 200},
            ],
            "subtotal": 300,
        }
        hints = SemanticHints(
            line_items_path="items",
            line_total_field="line_total",
            subtotal_path="subtotal",
        )
        report = validate_semantics(data, hints=hints)
        arith = [i for i in report.issues if i.category == "arithmetic"]
        assert len(arith) == 0  # 100+200=300, matches

    def test_items_without_line_total_field(self):
        data = {
            "items": [{"other_field": 100}],
            "subtotal": 100,
        }
        hints = SemanticHints(
            line_items_path="items",
            line_total_field="line_total",
            subtotal_path="subtotal",
        )
        report = validate_semantics(data, hints=hints)
        arith = [i for i in report.issues if i.category == "arithmetic"]
        assert len(arith) == 0  # No parseable = skip

    def test_negative_line_totals(self):
        """Credit notes with negative line totals."""
        data = {
            "items": [
                {"line_total": -100.0},
                {"line_total": -200.0},
            ],
            "subtotal": -300.0,
        }
        hints = SemanticHints(
            line_items_path="items",
            line_total_field="line_total",
            subtotal_path="subtotal",
        )
        report = validate_semantics(data, hints=hints)
        arith = [i for i in report.issues if i.category == "arithmetic"]
        assert len(arith) == 0  # -100 + -200 = -300

    def test_very_small_mismatch_tolerated(self):
        """Floating point: 0.001 mismatch should be tolerated (< 0.01)."""
        data = {
            "items": [{"line_total": 33.333}, {"line_total": 33.333}, {"line_total": 33.334}],
            "subtotal": 100.001,  # Slight mismatch
        }
        hints = SemanticHints(
            line_items_path="items",
            line_total_field="line_total",
            subtotal_path="subtotal",
        )
        report = validate_semantics(data, hints=hints)
        arith = [i for i in report.issues if i.category == "arithmetic"]
        assert len(arith) == 0


# ---------------------------------------------------------------------------
# Numeric coercion edge cases
# ---------------------------------------------------------------------------

class TestNumericCoercionEdgeCases:
    def test_nested_array_path(self):
        data = {"orders": [{"items": [{"qty": "five"}]}]}
        # Only handles one level of []
        hints = SemanticHints(numeric_fields=["orders[].items"])
        report = validate_semantics(data, hints=hints)
        # items is a list, not numeric — but the check only looks at scalars
        # This shouldn't crash
        assert isinstance(report, SemanticReport)

    def test_empty_array(self):
        data = {"items": []}
        hints = SemanticHints(numeric_fields=["items[].quantity"])
        report = validate_semantics(data, hints=hints)
        num = [i for i in report.issues if i.category == "numeric_coercion"]
        assert len(num) == 0

    def test_array_of_non_dicts(self):
        data = {"items": [1, 2, 3]}
        hints = SemanticHints(numeric_fields=["items[].quantity"])
        report = validate_semantics(data, hints=hints)
        num = [i for i in report.issues if i.category == "numeric_coercion"]
        assert len(num) == 0  # Non-dict items skipped

    def test_missing_field_in_item(self):
        data = {"items": [{"other": 5}]}
        hints = SemanticHints(numeric_fields=["items[].quantity"])
        report = validate_semantics(data, hints=hints)
        num = [i for i in report.issues if i.category == "numeric_coercion"]
        assert len(num) == 0  # None value skipped

    def test_scalar_path_missing(self):
        data = {}
        hints = SemanticHints(numeric_fields=["total"])
        report = validate_semantics(data, hints=hints)
        num = [i for i in report.issues if i.category == "numeric_coercion"]
        assert len(num) == 0  # Missing field skipped


# ---------------------------------------------------------------------------
# Completeness edge cases
# ---------------------------------------------------------------------------

class TestCompletenessEdgeCases:
    def test_nested_path(self):
        data = {"seller": {"name": ""}}
        hints = SemanticHints(nonempty_fields=["seller.name"])
        report = validate_semantics(data, hints=hints)
        comp = [i for i in report.issues if i.category == "completeness"]
        assert len(comp) == 1
        assert comp[0].path == "seller.name"

    def test_zero_is_not_empty(self):
        data = {"count": 0}
        hints = SemanticHints(nonempty_fields=["count"])
        report = validate_semantics(data, hints=hints)
        comp = [i for i in report.issues if i.category == "completeness"]
        assert len(comp) == 0  # 0 is a valid value

    def test_false_is_not_empty(self):
        data = {"flag": False}
        hints = SemanticHints(nonempty_fields=["flag"])
        report = validate_semantics(data, hints=hints)
        comp = [i for i in report.issues if i.category == "completeness"]
        assert len(comp) == 0  # False is a valid value

    def test_list_value_not_empty(self):
        data = {"items": [1, 2, 3]}
        hints = SemanticHints(nonempty_fields=["items"])
        report = validate_semantics(data, hints=hints)
        comp = [i for i in report.issues if i.category == "completeness"]
        assert len(comp) == 0


# ---------------------------------------------------------------------------
# Real invoice data
# ---------------------------------------------------------------------------

class TestRealInvoiceData:
    def test_invoice_data_with_full_hints(self):
        """Full hint set on real invoice data."""
        import json
        from pathlib import Path

        examples = Path(__file__).parent.parent / "examples"
        data = json.loads((examples / "invoice_data.json").read_text())

        hints = SemanticHints(
            line_items_path="items",
            line_total_field="amount",
            subtotal_path="subtotal",
            date_fields=["invoice_date", "due_date"],
            numeric_fields=["items[].qty"],
            nonempty_fields=["invoice_number", "sender.name", "recipient.name"],
        )
        report = validate_semantics(data, hints=hints)
        # Should have no errors (only possible warnings)
        assert not report.has_errors

    def test_einvoice_data(self):
        """E-invoice data with numeric amounts."""
        import json
        from pathlib import Path

        examples = Path(__file__).parent.parent / "examples"
        data_path = examples / "einvoice_data.json"
        if not data_path.exists():
            pytest.skip("einvoice_data.json not found")

        data = json.loads(data_path.read_text())
        hints = SemanticHints(
            line_items_path="items",
            line_total_field="line_total",
            subtotal_path="subtotal",
            date_fields=["invoice_date", "due_date"],
            numeric_fields=[
                "items[].quantity",
                "items[].unit_price",
                "items[].line_total",
            ],
            nonempty_fields=["invoice_number"],
        )
        report = validate_semantics(data, hints=hints)
        assert isinstance(report, SemanticReport)


# ---------------------------------------------------------------------------
# All issues are warnings by default
# ---------------------------------------------------------------------------

class TestSeverityDefaults:
    def test_all_issues_are_warnings(self):
        """Every issue type should default to warning, not error."""
        data = {
            "items": [{"line_total": "abc", "quantity": "xyz"}],
            "subtotal": 999,
            "invoice_date": "not-a-date",
            "invoice_number": "",
        }
        hints = SemanticHints(
            line_items_path="items",
            line_total_field="line_total",
            subtotal_path="subtotal",
            date_fields=["invoice_date"],
            numeric_fields=["items[].quantity"],
            nonempty_fields=["invoice_number"],
        )
        report = validate_semantics(data, hints=hints)
        for issue in report.issues:
            assert issue.severity == "warning", f"{issue.category} has severity={issue.severity}"

    def test_all_issues_are_deterministic(self):
        """All MVP checks should be deterministic."""
        data = {
            "items": [{"line_total": 100}],
            "subtotal": 999,
            "invoice_date": "bad",
            "invoice_number": "",
        }
        hints = SemanticHints(
            line_items_path="items",
            line_total_field="line_total",
            subtotal_path="subtotal",
            date_fields=["invoice_date"],
            nonempty_fields=["invoice_number"],
        )
        report = validate_semantics(data, hints=hints)
        for issue in report.issues:
            assert issue.deterministic is True
