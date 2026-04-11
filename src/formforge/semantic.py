"""Narrow semantic payload validation.

Beyond structural contract checks (field presence, type shape), detects
business-logic issues in the data that would produce wrong documents.

MVP checks (v1 — intentionally narrow):
  - arithmetic consistency (line item sums vs totals)
  - date parseability (standard formats)
  - completeness (required fields that are empty strings or None)
  - numeric coercion (fields expected to be numeric but are not)

NOT in v1: plausibility heuristics, format regularity scoring, currency
format guessing, consistency-across-renders.  Those get messy fast.

Semantic checks default to ``severity="warning"`` — they flag issues but
do not block rendering.  Callers who want to block can check
``report.has_errors``.

Usage::

    from formforge.semantic import validate_semantics

    report = validate_semantics(data, hints={"line_items": "items",
                                              "line_total": "line_total",
                                              "subtotal": "subtotal"})
    for issue in report.issues:
        print(f"{issue.path}: {issue.message}")
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SemanticIssue:
    """A semantic problem in the payload beyond structural correctness."""

    category: Literal["date_format", "arithmetic", "completeness", "numeric_coercion"]
    severity: Literal["error", "warning"]
    path: str                   # "items[3].line_total"
    message: str
    expected: str | None
    actual: str | None
    deterministic: bool         # True = math check; False = heuristic


@dataclass
class SemanticReport:
    """Result of semantic payload validation."""

    issues: list[SemanticIssue] = field(default_factory=list)
    checks_run: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.severity == "warning" for i in self.issues)

    def to_dict(self) -> dict:
        return {
            "issues": [
                {
                    "category": i.category,
                    "severity": i.severity,
                    "path": i.path,
                    "message": i.message,
                    "expected": i.expected,
                    "actual": i.actual,
                    "deterministic": i.deterministic,
                }
                for i in self.issues
            ],
            "checks_run": self.checks_run,
        }


# ---------------------------------------------------------------------------
# Semantic hints
# ---------------------------------------------------------------------------

@dataclass
class SemanticHints:
    """Opt-in field hints for semantic validation.

    Rather than guessing which fields are dates, totals, etc., the caller
    tells us. This avoids fragile heuristics.

    All fields are optional — checks only run for hinted fields.
    """

    # Arithmetic check: sum of line_total fields on items == subtotal
    line_items_path: str | None = None       # "items"
    line_total_field: str | None = None      # "line_total"
    subtotal_path: str | None = None         # "subtotal"

    # Date fields to check for parseability
    date_fields: list[str] | None = None     # ["invoice_date", "due_date"]

    # Fields that should be numeric
    numeric_fields: list[str] | None = None  # ["items[].quantity", "items[].unit_price"]

    # Required fields that must not be empty strings
    nonempty_fields: list[str] | None = None # ["invoice_number", "seller.name"]

    # Balance reconciliation: list of (summand_paths, expected_total_path).
    # Each check verifies: sum(values at summand_paths) == value at total_path.
    # Warnings only — does not block rendering.
    reconciliations: list[tuple[list[str], str]] | None = None


# Default hints for common invoice-like documents
INVOICE_HINTS = SemanticHints(
    line_items_path="items",
    line_total_field="line_total",
    subtotal_path="subtotal",
    date_fields=["invoice_date", "due_date"],
    numeric_fields=["items[].quantity", "items[].unit_price", "items[].line_total"],
    nonempty_fields=["invoice_number"],
)

RECEIPT_HINTS = SemanticHints(
    line_items_path="items",
    line_total_field="amount",
    subtotal_path="subtotal",
    date_fields=["date"],
    numeric_fields=[
        "items[].qty", "items[].unit_price", "items[].amount",
        "subtotal", "tax_amount", "total",
        "amount_tendered", "change_due",
    ],
    nonempty_fields=["receipt_number", "company.name"],
)

STATEMENT_HINTS = SemanticHints(
    line_items_path=None,
    line_total_field=None,
    subtotal_path=None,
    date_fields=["statement_date"],
    numeric_fields=[
        "opening_balance", "closing_balance",
        "total_charges", "total_payments",
        "aging.current", "aging.days_30",
        "aging.days_60", "aging.days_90", "aging.total",
    ],
    nonempty_fields=["customer.name", "customer.account_number"],
    reconciliations=[
        # aging buckets sum to aging total
        (["aging.current", "aging.days_30", "aging.days_60", "aging.days_90"], "aging.total"),
        # opening + charges + payments = closing
        (["opening_balance", "total_charges", "total_payments"], "closing_balance"),
    ],
)


# ---------------------------------------------------------------------------
# Value extraction helpers
# ---------------------------------------------------------------------------

def _resolve_path(data: dict, path: str) -> object | None:
    """Resolve a dot-notation path like 'seller.name' to a value.

    Returns None if any segment is missing.
    """
    parts = path.split(".")
    current: object = data
    for part in parts:
        if isinstance(current, dict):
            if part not in current:
                return None
            current = current[part]
        else:
            return None
    return current


def _try_parse_number(value: object) -> float | None:
    """Try to parse a value as a number. Returns None if not numeric."""
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        # Strip currency symbols and whitespace
        cleaned = re.sub(r'[€$£¥\s,]', '', value)
        # Handle negative in parens: (500.00)
        if cleaned.startswith('(') and cleaned.endswith(')'):
            cleaned = '-' + cleaned[1:-1]
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


# Common date formats to try
_DATE_FORMATS = [
    "%Y-%m-%d",          # 2026-04-10
    "%m/%d/%Y",          # 04/10/2026
    "%d/%m/%Y",          # 10/04/2026
    "%d.%m.%Y",          # 10.04.2026
    "%B %d, %Y",         # April 10, 2026
    "%b %d, %Y",         # Apr 10, 2026
    "%b %d",             # Apr 10
    "%Y-%m-%dT%H:%M:%S", # ISO 8601
]


def _try_parse_date(value: str) -> bool:
    """Check if a string is parseable as a date."""
    for fmt in _DATE_FORMATS:
        try:
            datetime.strptime(value, fmt)
            return True
        except ValueError:
            continue
    return False


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_arithmetic(
    data: dict,
    hints: SemanticHints,
    issues: list[SemanticIssue],
) -> None:
    """Check that line item totals sum to the stated subtotal."""
    if not (hints.line_items_path and hints.line_total_field and hints.subtotal_path):
        return

    items = _resolve_path(data, hints.line_items_path)
    if not isinstance(items, list):
        return

    subtotal_raw = _resolve_path(data, hints.subtotal_path)
    subtotal = _try_parse_number(subtotal_raw)
    if subtotal is None:
        return  # Can't check if subtotal isn't numeric

    computed_sum = 0.0
    parseable_count = 0
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        val = item.get(hints.line_total_field)
        parsed = _try_parse_number(val)
        if parsed is not None:
            computed_sum += parsed
            parseable_count += 1

    if parseable_count == 0:
        return  # No numeric line totals found

    # Compare with tolerance for floating-point
    if abs(computed_sum - subtotal) > 0.01:
        issues.append(SemanticIssue(
            category="arithmetic",
            severity="warning",
            path=hints.subtotal_path,
            message=f"sum({hints.line_items_path}[].{hints.line_total_field}) = {computed_sum:.2f}, but {hints.subtotal_path} = {subtotal:.2f}",
            expected=f"{computed_sum:.2f}",
            actual=f"{subtotal:.2f}" if subtotal_raw is not None else None,
            deterministic=True,
        ))


def _check_dates(
    data: dict,
    hints: SemanticHints,
    issues: list[SemanticIssue],
) -> None:
    """Check that date fields contain parseable date strings."""
    if not hints.date_fields:
        return

    for field_path in hints.date_fields:
        value = _resolve_path(data, field_path)
        if value is None:
            continue  # Missing field handled by contract validation
        if not isinstance(value, str):
            issues.append(SemanticIssue(
                category="date_format",
                severity="warning",
                path=field_path,
                message=f"Expected date string, got {type(value).__name__}",
                expected="date string",
                actual=str(type(value).__name__),
                deterministic=True,
            ))
            continue
        if value and not _try_parse_date(value):
            issues.append(SemanticIssue(
                category="date_format",
                severity="warning",
                path=field_path,
                message=f"Cannot parse as date: '{value}'",
                expected="parseable date",
                actual=f"'{value}'",
                deterministic=True,
            ))


def _check_completeness(
    data: dict,
    hints: SemanticHints,
    issues: list[SemanticIssue],
) -> None:
    """Check that required fields are not empty strings or None."""
    if not hints.nonempty_fields:
        return

    for field_path in hints.nonempty_fields:
        value = _resolve_path(data, field_path)
        if value is None:
            issues.append(SemanticIssue(
                category="completeness",
                severity="warning",
                path=field_path,
                message=f"Required field is None or missing",
                expected="non-empty value",
                actual="None",
                deterministic=True,
            ))
        elif isinstance(value, str) and value.strip() == "":
            issues.append(SemanticIssue(
                category="completeness",
                severity="warning",
                path=field_path,
                message=f"Required field is empty string",
                expected="non-empty value",
                actual='""',
                deterministic=True,
            ))


def _check_numeric_coercion(
    data: dict,
    hints: SemanticHints,
    issues: list[SemanticIssue],
) -> None:
    """Check that fields expected to be numeric can be parsed as numbers.

    Handles array paths like 'items[].quantity' by iterating over the
    array and checking each element.
    """
    if not hints.numeric_fields:
        return

    for field_spec in hints.numeric_fields:
        # Handle array fields: "items[].quantity"
        if "[]." in field_spec:
            array_path, item_field = field_spec.split("[].", 1)
            items = _resolve_path(data, array_path)
            if not isinstance(items, list):
                continue
            for i, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                val = item.get(item_field)
                if val is None:
                    continue
                if _try_parse_number(val) is None:
                    issues.append(SemanticIssue(
                        category="numeric_coercion",
                        severity="warning",
                        path=f"{array_path}[{i}].{item_field}",
                        message=f"Expected numeric value, got '{val}'",
                        expected="numeric",
                        actual=str(val),
                        deterministic=True,
                    ))
        else:
            # Simple scalar field
            val = _resolve_path(data, field_spec)
            if val is None:
                continue
            if _try_parse_number(val) is None:
                issues.append(SemanticIssue(
                    category="numeric_coercion",
                    severity="warning",
                    path=field_spec,
                    message=f"Expected numeric value, got '{val}'",
                    expected="numeric",
                    actual=str(val),
                    deterministic=True,
                ))


def _check_reconciliation(
    data: dict,
    hints: SemanticHints,
    issues: list[SemanticIssue],
) -> None:
    """Check that groups of numeric fields sum to expected totals."""
    if not hints.reconciliations:
        return

    for summand_paths, total_path in hints.reconciliations:
        total_raw = _resolve_path(data, total_path)
        expected = _try_parse_number(total_raw)
        if expected is None:
            continue  # Can't check if total isn't numeric

        summands: list[float] = []
        all_parseable = True
        for sp in summand_paths:
            val = _try_parse_number(_resolve_path(data, sp))
            if val is None:
                all_parseable = False
                break
            summands.append(val)

        if not all_parseable:
            continue  # Skip if any summand isn't parseable

        actual_sum = sum(summands)
        if abs(actual_sum - expected) > 0.01:
            paths_str = " + ".join(summand_paths)
            issues.append(SemanticIssue(
                category="arithmetic",
                severity="warning",
                path=total_path,
                message=f"{paths_str} = {actual_sum:.2f}, but {total_path} = {expected:.2f}",
                expected=f"{actual_sum:.2f}",
                actual=f"{expected:.2f}",
                deterministic=True,
            ))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_semantics(
    data: dict,
    hints: SemanticHints | None = None,
) -> SemanticReport:
    """Run semantic validation on a data payload.

    Args:
        data: The data dict to validate.
        hints: Opt-in field hints. If None, no checks run (semantic
            validation is hint-driven, not inference-driven).

    Returns:
        SemanticReport with issues found. Empty if no hints provided.
    """
    if hints is None:
        return SemanticReport(checks_run=[])

    issues: list[SemanticIssue] = []
    checks_run: list[str] = []

    _check_arithmetic(data, hints, issues)
    checks_run.append("arithmetic_consistency")

    _check_dates(data, hints, issues)
    checks_run.append("date_parseable")

    _check_completeness(data, hints, issues)
    checks_run.append("required_field_empty")

    _check_numeric_coercion(data, hints, issues)
    checks_run.append("numeric_coercion")

    _check_reconciliation(data, hints, issues)
    checks_run.append("balance_reconciliation")

    return SemanticReport(issues=issues, checks_run=checks_run)
