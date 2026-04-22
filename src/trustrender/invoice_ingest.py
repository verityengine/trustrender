"""Structured invoice ingestion pipeline.

Takes messy real-world invoice data and compiles it into a canonical
payload ready for rendering, with full provenance and validation.

Seven pipeline stages:
  1. _resolve_field_names  — alias map lookups at all nesting levels
  2. _coerce_types         — string amounts to numbers, dates to YYYY-MM-DD
  3. _compute_missing      — line_totals, subtotal, tax_amount, total
  4. _classify_unknown      — near_match / suspicious / pass_through
  5. _validate_semantics   — arithmetic, dates, completeness, identity
  6. _build_canonical      — construct CanonicalInvoice dataclass
  7. _reshape_for_template — emit dict matching invoice.j2.typ shape

Public API::

    from trustrender.invoice_ingest import ingest_invoice
    report = ingest_invoice(messy_data)
    if report.render_ready:
        pdf = render("invoice.j2.typ", report.template_payload)
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal

from trustrender.invoice_aliases import (
    CANONICAL_ITEM,
    CANONICAL_PARTY,
    CANONICAL_TOP_LEVEL,
    FLAT_RECIPIENT_FIELDS,
    FLAT_SENDER_FIELDS,
    ITEM_ALIASES,
    PARTY_ALIASES,
    TOP_LEVEL_ALIASES,
    classify_unknown,
    find_near_match,
)
from trustrender.invoice_schema import (
    Address,
    CanonicalInvoice,
    FieldProvenance,
    LineItem,
)

# ---------------------------------------------------------------------------
# Report data structures
# ---------------------------------------------------------------------------


@dataclass
class ValidationResult:
    rule_id: str
    severity: Literal["blocked", "error", "warning", "info"]
    passed: bool
    message: str
    path: str = ""
    expected: str | None = None
    actual: str | None = None

    def to_dict(self) -> dict:
        d: dict = {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "passed": self.passed,
            "message": self.message,
        }
        if self.path:
            d["path"] = self.path
        if self.expected is not None:
            d["expected"] = self.expected
        if self.actual is not None:
            d["actual"] = self.actual
        return d


@dataclass
class UnknownField:
    path: str
    value: Any
    classification: Literal["near_match", "suspicious", "pass_through"]
    suggestion: str | None = None
    edit_distance: int | None = None

    def to_dict(self) -> dict:
        d: dict = {
            "path": self.path,
            "classification": self.classification,
        }
        if self.suggestion is not None:
            d["suggestion"] = self.suggestion
        if self.edit_distance is not None:
            d["edit_distance"] = self.edit_distance
        # Omit value from serialization — could be large
        return d


@dataclass
class IngestionReport:
    status: Literal["ready", "ready_with_warnings", "blocked"]
    render_ready: bool
    canonical: dict
    template_payload: dict | None  # None when blocked — prevents accidental downstream use
    errors: list[ValidationResult] = field(default_factory=list)
    warnings: list[ValidationResult] = field(default_factory=list)
    normalizations: list[FieldProvenance] = field(default_factory=list)
    computed_fields: list[str] = field(default_factory=list)
    unknown_fields: list[UnknownField] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "render_ready": self.render_ready,
            "canonical": self.canonical,
            "template_payload": self.template_payload,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "normalizations": [n.to_dict() for n in self.normalizations],
            "computed_fields": self.computed_fields,
            "unknown_fields": [u.to_dict() for u in self.unknown_fields],
        }


# ---------------------------------------------------------------------------
# Type coercion helpers
# ---------------------------------------------------------------------------

# Common date formats (same as semantic.py)
_DATE_FORMATS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%d/%m/%Y",
    "%d.%m.%Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%b %d",
    "%Y-%m-%dT%H:%M:%S",
]

# European decimal pattern: ends with comma + 1-2 digits
_EUROPEAN_DECIMAL_RE = re.compile(r"^-?[\d.]+,\d{1,2}$")


def _try_parse_number(value: object) -> float | None:
    """Parse a value as a number. Strips currency symbols and commas."""
    if isinstance(value, (int, float)):
        result = float(value)
        return result if math.isfinite(result) else None
    if not isinstance(value, str):
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    # Strip currency symbols and whitespace
    cleaned = re.sub(r"[€$£¥\s]", "", cleaned)
    # Strip trailing %
    cleaned = cleaned.rstrip("%").strip()
    # Handle European decimals: "1.234,56" -> "1234.56"
    if _EUROPEAN_DECIMAL_RE.match(cleaned):
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        # Standard: strip commas as thousands separators
        cleaned = cleaned.replace(",", "")
    # Handle negative in parens: (500.00) -> -500.00
    if cleaned.startswith("(") and cleaned.endswith(")"):
        cleaned = "-" + cleaned[1:-1]
    try:
        result = float(cleaned)
    except ValueError:
        return None
    return result if math.isfinite(result) else None


def _try_parse_date(value: str) -> str | None:
    """Parse a date string and return YYYY-MM-DD, or None if unparseable."""
    if not isinstance(value, str) or not value.strip():
        return None
    value = value.strip()
    # Already ISO format
    if re.match(r"^\d{4}-\d{2}-\d{2}$", value):
        return value
    for fmt in _DATE_FORMATS:
        try:
            dt = datetime.strptime(value, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Stage 0: Pre-process structural variations
# ---------------------------------------------------------------------------


def _preprocess_structure(
    data: dict,
    normalizations: list[FieldProvenance],
) -> dict:
    """Handle generic structural patterns before field name resolution.

    Three generic normalizations (no source-specific logic):
    1. Root unwrap: {"invoice": {...}} -> {...}
    2. Nested list extraction: {"lines": {"data": [...]}} -> {"lines": [...]}
    3. Flat party synthesis: bill_from_name/account_name -> sender.{name}
    """
    # 1. Root unwrap: if "invoice" is a top-level key wrapping the invoice object,
    # unwrap it and merge siblings at the top level (handles Freshbooks pattern).
    invoice_val = data.get("invoice") or data.get("Invoice")
    invoice_key = "invoice" if "invoice" in data else ("Invoice" if "Invoice" in data else None)
    if invoice_key is not None and isinstance(invoice_val, dict):
        other = {k: v for k, v in data.items() if k != invoice_key}
        data = {**invoice_val, **other}
        normalizations.append(
            FieldProvenance(
                canonical_name="(root)",
                source="alias",
                original_key=invoice_key,
                message=f"unwrapped root key {invoice_key!r}",
            )
        )

    # 2. Nested list extraction: if any item-like key holds {"data": [...]} unwrap it
    for key in list(data.keys()):
        val = data[key]
        if (
            isinstance(val, dict)
            and "data" in val
            and isinstance(val["data"], list)
            and key in (set(TOP_LEVEL_ALIASES) | {"items", "lines", "Line", "LineItems"})
        ):
            data[key] = val["data"]
            normalizations.append(
                FieldProvenance(
                    canonical_name="items",
                    source="alias",
                    original_key=key,
                    message=f"extracted {key}.data[] list ({len(data[key])} items)",
                )
            )

    # 3. Flat party synthesis: extract bill_from_*/account_* into sender/recipient objects
    sender_parts: dict[str, Any] = {}
    recipient_parts: dict[str, Any] = {}
    consumed: list[str] = []

    for key, value in data.items():
        if key in FLAT_SENDER_FIELDS:
            sub_field = FLAT_SENDER_FIELDS[key]
            sender_parts[sub_field] = value
            consumed.append(key)
            normalizations.append(
                FieldProvenance(
                    canonical_name=f"sender.{sub_field}",
                    source="alias",
                    original_key=key,
                    message=f"{key!r} -> sender.{sub_field!r}",
                )
            )
        elif key in FLAT_RECIPIENT_FIELDS:
            sub_field = FLAT_RECIPIENT_FIELDS[key]
            recipient_parts[sub_field] = value
            consumed.append(key)
            normalizations.append(
                FieldProvenance(
                    canonical_name=f"recipient.{sub_field}",
                    source="alias",
                    original_key=key,
                    message=f"{key!r} -> recipient.{sub_field!r}",
                )
            )

    for key in consumed:
        del data[key]

    # Merge synthesized parties — don't overwrite if a real sender/recipient object exists
    if sender_parts and "sender" not in data:
        data["sender"] = sender_parts
    if recipient_parts and "recipient" not in data:
        data["recipient"] = recipient_parts

    return data


# ---------------------------------------------------------------------------
# Stage 1: Resolve field names
# ---------------------------------------------------------------------------


def _resolve_field_names(
    data: dict,
    normalizations: list[FieldProvenance],
) -> dict:
    """Resolve aliases at all nesting levels. Returns new dict with canonical keys."""
    resolved: dict = {}

    for key, value in data.items():
        # Check if already canonical
        if key in CANONICAL_TOP_LEVEL:
            canonical = key
            # Recurse into party objects
            if canonical in ("sender", "recipient") and isinstance(value, dict):
                value = _resolve_party_fields(value, canonical, normalizations)
            # Recurse into items list
            elif canonical == "items" and isinstance(value, list):
                value = [_resolve_item_fields(item, i, normalizations) if isinstance(item, dict) else item for i, item in enumerate(value)]
            resolved[canonical] = value
            normalizations.append(
                FieldProvenance(
                    canonical_name=canonical,
                    source="exact",
                )
            )
            continue

        # Check alias map
        alias_target = TOP_LEVEL_ALIASES.get(key)
        if alias_target is not None:
            # Don't overwrite if canonical key already exists
            if alias_target not in resolved:
                mapped_value = value
                if alias_target in ("sender", "recipient") and isinstance(value, dict):
                    mapped_value = _resolve_party_fields(value, alias_target, normalizations)
                elif alias_target == "items" and isinstance(value, list):
                    mapped_value = [
                        _resolve_item_fields(item, i, normalizations) if isinstance(item, dict) else item for i, item in enumerate(value)
                    ]
                resolved[alias_target] = mapped_value
                normalizations.append(
                    FieldProvenance(
                        canonical_name=alias_target,
                        source="alias",
                        original_key=key,
                        message=f"{key!r} -> {alias_target!r}",
                    )
                )
            continue

        # Unknown field — keep for later classification
        resolved.setdefault("_unknown", {})[key] = value

    return resolved


def _resolve_party_fields(
    data: dict,
    parent: str,
    normalizations: list[FieldProvenance],
) -> dict:
    """Resolve aliases in a party (sender/recipient) sub-object."""
    resolved: dict = {}
    for key, value in data.items():
        if key in CANONICAL_PARTY:
            resolved[key] = value
            normalizations.append(
                FieldProvenance(
                    canonical_name=f"{parent}.{key}",
                    source="exact",
                )
            )
        else:
            alias_target = PARTY_ALIASES.get(key)
            if alias_target is not None and alias_target not in resolved:
                resolved[alias_target] = value
                normalizations.append(
                    FieldProvenance(
                        canonical_name=f"{parent}.{alias_target}",
                        source="alias",
                        original_key=key,
                        message=f"{parent}.{key!r} -> {parent}.{alias_target!r}",
                    )
                )
            else:
                resolved.setdefault("_unknown", {})[key] = value
    return resolved


def _resolve_item_fields(
    data: dict,
    index: int,
    normalizations: list[FieldProvenance],
) -> dict:
    """Resolve aliases in a line item sub-object."""
    resolved: dict = {}
    for key, value in data.items():
        if key in CANONICAL_ITEM:
            resolved[key] = value
            normalizations.append(
                FieldProvenance(
                    canonical_name=f"items[{index}].{key}",
                    source="exact",
                )
            )
        else:
            alias_target = ITEM_ALIASES.get(key)
            if alias_target is not None and alias_target not in resolved:
                resolved[alias_target] = value
                normalizations.append(
                    FieldProvenance(
                        canonical_name=f"items[{index}].{alias_target}",
                        source="alias",
                        original_key=key,
                        message=f"items[{index}].{key!r} -> items[{index}].{alias_target!r}",
                    )
                )
            else:
                resolved.setdefault("_unknown", {})[key] = value
    return resolved


# ---------------------------------------------------------------------------
# Stage 2: Coerce types
# ---------------------------------------------------------------------------

_NUMERIC_FIELDS_TOP = {"subtotal", "tax_rate", "tax_amount", "total"}
_NUMERIC_FIELDS_ITEM = {"quantity", "unit_price", "line_total", "num"}
_DATE_FIELDS = {"invoice_date", "due_date"}


def _unwrap_money_dict(val: object) -> object:
    """If a value is a money object like {amount: ..., code: ...}, return the amount.

    Generic rule: any dict with an "amount" key where the dict is sitting in a
    numeric field slot is treated as a scalar money value. The code/currency field
    is discarded here — currency is captured separately at the top level.
    """
    if isinstance(val, dict) and "amount" in val:
        return val["amount"]
    return val


def _coerce_types(
    data: dict,
    normalizations: list[FieldProvenance],
) -> dict:
    """Coerce string values to proper types in-place."""
    # Top-level numeric fields
    for field_name in _NUMERIC_FIELDS_TOP:
        if field_name in data:
            original = data[field_name]
            # Unwrap money dict before numeric parse: {amount: ..., code: ...} -> amount
            unwrapped = _unwrap_money_dict(original)
            if unwrapped is not original:
                normalizations.append(
                    FieldProvenance(
                        canonical_name=field_name,
                        source="alias",
                        original_value=str(original),
                        message=f"unwrapped money object {field_name!r}.amount -> scalar",
                    )
                )
                original = unwrapped
                data[field_name] = unwrapped
            parsed = _try_parse_number(original)
            if parsed is not None and not isinstance(original, (int, float)):
                data[field_name] = parsed
                normalizations.append(
                    FieldProvenance(
                        canonical_name=field_name,
                        source="alias",  # type coercion reported as normalization
                        original_value=str(original),
                        message=f"coerced {original!r} -> {parsed}",
                    )
                )

    # Date fields
    for field_name in _DATE_FIELDS:
        if field_name in data:
            original = data[field_name]
            if isinstance(original, str):
                parsed = _try_parse_date(original)
                if parsed is not None and parsed != original:
                    data[field_name] = parsed
                    normalizations.append(
                        FieldProvenance(
                            canonical_name=field_name,
                            source="alias",
                            original_value=original,
                            message=f"date {original!r} -> {parsed!r}",
                        )
                    )

    # Item-level numeric fields
    items = data.get("items", [])
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        for field_name in _NUMERIC_FIELDS_ITEM:
            if field_name in item:
                original = item[field_name]
                # Unwrap money dict before numeric parse
                unwrapped = _unwrap_money_dict(original)
                if unwrapped is not original:
                    normalizations.append(
                        FieldProvenance(
                            canonical_name=f"items[{i}].{field_name}",
                            source="alias",
                            original_value=str(original),
                            message=f"unwrapped money object items[{i}].{field_name!r}.amount -> scalar",
                        )
                    )
                    original = unwrapped
                    item[field_name] = unwrapped
                parsed = _try_parse_number(original)
                if parsed is not None and not isinstance(original, (int, float)):
                    item[field_name] = parsed
                    normalizations.append(
                        FieldProvenance(
                            canonical_name=f"items[{i}].{field_name}",
                            source="alias",
                            original_value=str(original),
                            message=f"coerced {original!r} -> {parsed}",
                        )
                    )

    return data


# ---------------------------------------------------------------------------
# Stage 3: Compute missing values
# ---------------------------------------------------------------------------


def _compute_missing(
    data: dict,
    normalizations: list[FieldProvenance],
    computed_fields: list[str],
) -> dict:
    """Compute missing totals from available data. Never overrides explicit values."""
    items = data.get("items", [])

    # Auto-assign item numbers if missing
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        if "num" not in item or not item["num"]:
            item["num"] = i + 1
            normalizations.append(
                FieldProvenance(
                    canonical_name=f"items[{i}].num",
                    source="computed",
                    message=f"auto-assigned item number {i + 1}",
                )
            )
            computed_fields.append(f"items[{i}].num")

    # Compute line_total if missing
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        qty = item.get("quantity")
        price = item.get("unit_price")
        if "line_total" not in item or item.get("line_total") is None:
            if isinstance(qty, (int, float)) and isinstance(price, (int, float)):
                computed = round(qty * price, 2)
                item["line_total"] = computed
                normalizations.append(
                    FieldProvenance(
                        canonical_name=f"items[{i}].line_total",
                        source="computed",
                        message=f"computed {qty} * {price} = {computed}",
                    )
                )
                computed_fields.append(f"items[{i}].line_total")

    # Compute subtotal if missing
    if "subtotal" not in data or data.get("subtotal") is None:
        line_totals = [
            item.get("line_total", 0) for item in items if isinstance(item, dict) and isinstance(item.get("line_total"), (int, float))
        ]
        if line_totals:
            computed = round(sum(line_totals), 2)
            data["subtotal"] = computed
            normalizations.append(
                FieldProvenance(
                    canonical_name="subtotal",
                    source="computed",
                    message=f"computed sum of {len(line_totals)} line totals = {computed}",
                )
            )
            computed_fields.append("subtotal")

    # Compute tax_amount if missing and tax_rate is present
    if "tax_amount" not in data or data.get("tax_amount") is None:
        subtotal = data.get("subtotal")
        tax_rate = data.get("tax_rate")
        if isinstance(subtotal, (int, float)) and isinstance(tax_rate, (int, float)) and tax_rate > 0:
            computed = round(subtotal * tax_rate / 100, 2)
            data["tax_amount"] = computed
            normalizations.append(
                FieldProvenance(
                    canonical_name="tax_amount",
                    source="computed",
                    message=f"computed {subtotal} * {tax_rate}% = {computed}",
                )
            )
            computed_fields.append("tax_amount")

    # Compute total if missing
    if "total" not in data or data.get("total") is None:
        subtotal = data.get("subtotal")
        tax_amount = data.get("tax_amount", 0)
        if isinstance(subtotal, (int, float)):
            if not isinstance(tax_amount, (int, float)):
                tax_amount = 0
            computed = round(subtotal + tax_amount, 2)
            data["total"] = computed
            normalizations.append(
                FieldProvenance(
                    canonical_name="total",
                    source="computed",
                    message=f"computed {subtotal} + {tax_amount} = {computed}",
                )
            )
            computed_fields.append("total")

    # Default currency
    if "currency" not in data or not data.get("currency"):
        data["currency"] = "USD"
        normalizations.append(
            FieldProvenance(
                canonical_name="currency",
                source="default",
                message="defaulted to USD",
            )
        )
        computed_fields.append("currency")

    return data


# ---------------------------------------------------------------------------
# Stage 4: Classify unknown fields
# ---------------------------------------------------------------------------


def _classify_unknown_fields(
    data: dict,
    unknown_fields: list[UnknownField],
) -> dict:
    """Classify unknown fields and move them to extras."""
    extras: dict = {}
    unknown_raw = data.pop("_unknown", {})

    for key, value in unknown_raw.items():
        # Check near-match first
        match = find_near_match(key, CANONICAL_TOP_LEVEL)
        if match is not None:
            suggestion, distance = match
            unknown_fields.append(
                UnknownField(
                    path=key,
                    value=value,
                    classification="near_match",
                    suggestion=suggestion,
                    edit_distance=distance,
                )
            )
        else:
            classification = classify_unknown(key)
            unknown_fields.append(
                UnknownField(
                    path=key,
                    value=value,
                    classification=classification,
                )
            )
        extras[key] = value

    # Also collect unknown fields from party objects
    for party_key in ("sender", "recipient"):
        party = data.get(party_key)
        if isinstance(party, dict):
            party_unknown = party.pop("_unknown", {})
            for key, value in party_unknown.items():
                path = f"{party_key}.{key}"
                match = find_near_match(key, CANONICAL_PARTY)
                if match is not None:
                    suggestion, distance = match
                    unknown_fields.append(
                        UnknownField(
                            path=path,
                            value=value,
                            classification="near_match",
                            suggestion=f"{party_key}.{suggestion}",
                            edit_distance=distance,
                        )
                    )
                else:
                    unknown_fields.append(
                        UnknownField(
                            path=path,
                            value=value,
                            classification=classify_unknown(key),
                        )
                    )
                extras[path] = value

    # Unknown fields from items
    items = data.get("items", [])
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        item_unknown = item.pop("_unknown", {})
        for key, value in item_unknown.items():
            path = f"items[{i}].{key}"
            match = find_near_match(key, CANONICAL_ITEM)
            if match is not None:
                suggestion, distance = match
                unknown_fields.append(
                    UnknownField(
                        path=path,
                        value=value,
                        classification="near_match",
                        suggestion=f"items[].{suggestion}",
                        edit_distance=distance,
                    )
                )
            else:
                unknown_fields.append(
                    UnknownField(
                        path=path,
                        value=value,
                        classification=classify_unknown(key),
                    )
                )
            extras[path] = value

    data["_extras"] = extras
    return data


# ---------------------------------------------------------------------------
# Stage 5: Validate semantics
# ---------------------------------------------------------------------------

_TOLERANCE = 0.01  # rounding tolerance for arithmetic checks


def _validate_semantics(
    data: dict,
    errors: list[ValidationResult],
    warnings: list[ValidationResult],
) -> None:
    """Run semantic validation rules. Populates errors and warnings lists."""

    # --- Blocked checks ---

    invoice_number = data.get("invoice_number")
    if not invoice_number or (isinstance(invoice_number, str) and not invoice_number.strip()):
        errors.append(
            ValidationResult(
                rule_id="identity.invoice_number",
                severity="blocked",
                passed=False,
                message="invoice_number is missing or empty — render blocked",
                path="invoice_number",
            )
        )

    items = data.get("items", [])
    if not items:
        errors.append(
            ValidationResult(
                rule_id="items.non_empty",
                severity="blocked",
                passed=False,
                message="no line items — render blocked",
                path="items",
            )
        )

    # --- Blocked checks: identity ---

    sender = data.get("sender", {})
    if not isinstance(sender, dict) or not sender.get("name"):
        errors.append(
            ValidationResult(
                rule_id="identity.sender_name",
                severity="blocked",
                passed=False,
                message="sender.name is missing or empty — render blocked",
                path="sender.name",
            )
        )

    recipient = data.get("recipient", {})
    if not isinstance(recipient, dict) or not recipient.get("name"):
        errors.append(
            ValidationResult(
                rule_id="identity.recipient_name",
                severity="blocked",
                passed=False,
                message="recipient.name is missing or empty — render blocked",
                path="recipient.name",
            )
        )

    # --- Blocked checks: arithmetic contradictions ---
    # A known arithmetic contradiction means the payload is internally inconsistent.
    # We do not override the caller's values — we block render and report the truth.

    # Arithmetic: line_total vs quantity * unit_price
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        qty = item.get("quantity")
        price = item.get("unit_price")
        lt = item.get("line_total")
        if isinstance(qty, (int, float)) and isinstance(price, (int, float)) and isinstance(lt, (int, float)):
            expected = round(qty * price, 2)
            if abs(lt - expected) > _TOLERANCE:
                errors.append(
                    ValidationResult(
                        rule_id="arithmetic.line_total",
                        severity="blocked",
                        passed=False,
                        message=f"items[{i}].line_total ({lt}) != quantity ({qty}) * unit_price ({price}) = {expected} — render blocked",
                        path=f"items[{i}].line_total",
                        expected=str(expected),
                        actual=str(lt),
                    )
                )

    # Arithmetic: subtotal vs sum of line_totals
    subtotal = data.get("subtotal")
    if isinstance(subtotal, (int, float)) and items:
        line_totals = [
            item.get("line_total", 0) for item in items if isinstance(item, dict) and isinstance(item.get("line_total"), (int, float))
        ]
        if line_totals:
            expected_sub = round(sum(line_totals), 2)
            if abs(subtotal - expected_sub) > _TOLERANCE:
                errors.append(
                    ValidationResult(
                        rule_id="arithmetic.subtotal",
                        severity="blocked",
                        passed=False,
                        message=f"subtotal ({subtotal}) != sum of line totals ({expected_sub}) — render blocked",
                        path="subtotal",
                        expected=str(expected_sub),
                        actual=str(subtotal),
                    )
                )

    # Arithmetic: total vs subtotal + tax_amount
    total = data.get("total")
    tax_amount = data.get("tax_amount", 0)
    if isinstance(total, (int, float)) and isinstance(subtotal, (int, float)):
        if not isinstance(tax_amount, (int, float)):
            tax_amount = 0
        expected_total = round(subtotal + tax_amount, 2)
        if abs(total - expected_total) > _TOLERANCE:
            errors.append(
                ValidationResult(
                    rule_id="arithmetic.total",
                    severity="blocked",
                    passed=False,
                    message=f"total ({total}) != subtotal ({subtotal}) + tax_amount ({tax_amount}) = {expected_total} — render blocked",
                    path="total",
                    expected=str(expected_total),
                    actual=str(total),
                )
            )

    # --- Error checks: date format ---

    for field_name in ("invoice_date", "due_date"):
        val = data.get(field_name)
        if isinstance(val, str) and val.strip():
            parsed = _try_parse_date(val)
            if parsed is None:
                errors.append(
                    ValidationResult(
                        rule_id="date.parseable",
                        severity="error",
                        passed=False,
                        message=f"{field_name} ({val!r}) is not a recognized date format",
                        path=field_name,
                    )
                )

    # --- Warning checks ---

    # Date ordering
    inv_date = data.get("invoice_date")
    due = data.get("due_date")
    if isinstance(inv_date, str) and isinstance(due, str):
        inv_parsed = _try_parse_date(inv_date)
        due_parsed = _try_parse_date(due)
        if inv_parsed and due_parsed and due_parsed < inv_parsed:
            warnings.append(
                ValidationResult(
                    rule_id="date.ordering",
                    severity="warning",
                    passed=False,
                    message=f"due_date ({due}) is before invoice_date ({inv_date})",
                    path="due_date",
                )
            )

    # Negative amounts
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        for field_name in ("quantity", "unit_price"):
            val = item.get(field_name)
            if isinstance(val, (int, float)) and val < 0:
                warnings.append(
                    ValidationResult(
                        rule_id="items.positive_amounts",
                        severity="warning",
                        passed=False,
                        message=f"items[{i}].{field_name} is negative ({val})",
                        path=f"items[{i}].{field_name}",
                    )
                )


# ---------------------------------------------------------------------------
# Stage 6: Build canonical
# ---------------------------------------------------------------------------


def _build_canonical(data: dict) -> CanonicalInvoice:
    """Construct CanonicalInvoice from resolved + coerced + computed data."""
    sender_data = data.get("sender", {})
    if not isinstance(sender_data, dict):
        sender_data = {}
    recipient_data = data.get("recipient", {})
    if not isinstance(recipient_data, dict):
        recipient_data = {}

    sender = Address(
        name=str(sender_data.get("name", "")),
        address=str(sender_data.get("address", "")),
        email=str(sender_data.get("email", "")),
    )
    recipient = Address(
        name=str(recipient_data.get("name", "")),
        address=str(recipient_data.get("address", "")),
        email=str(recipient_data.get("email", "")),
    )

    def _safe_float(val: object) -> float:
        if isinstance(val, (int, float)):
            return float(val)
        return 0.0

    def _safe_int(val: object) -> int:
        if isinstance(val, (int, float)):
            return int(val)
        return 0

    raw_items = data.get("items", [])
    items: list[LineItem] = []
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        items.append(
            LineItem(
                description=str(item.get("description", "")),
                quantity=_safe_float(item.get("quantity", 0)),
                unit_price=_safe_float(item.get("unit_price", 0)),
                line_total=_safe_float(item.get("line_total", 0)),
                num=_safe_int(item.get("num", 0)),
            )
        )

    def _num(key: str) -> float:
        val = data.get(key, 0)
        return float(val) if isinstance(val, (int, float)) else 0.0

    return CanonicalInvoice(
        invoice_number=str(data.get("invoice_number", "")),
        invoice_date=str(data.get("invoice_date", "")),
        due_date=str(data.get("due_date", "")),
        sender=sender,
        recipient=recipient,
        items=items,
        subtotal=_num("subtotal"),
        tax_rate=_num("tax_rate"),
        tax_amount=_num("tax_amount"),
        total=_num("total"),
        currency=str(data.get("currency", "USD")),
        payment_terms=str(data.get("payment_terms", "")),
        notes=str(data.get("notes", "")),
        extras=data.get("_extras", {}),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def ingest_invoice(data: dict) -> IngestionReport:
    """Ingest messy invoice data into a canonical renderable payload.

    Args:
        data: Messy invoice data dict (any field names, string types, etc.)

    Returns:
        IngestionReport with canonical payload, template_payload for
        invoice.j2.typ, validation results, and full provenance.
    """
    if not isinstance(data, dict):
        return IngestionReport(
            status="blocked",
            render_ready=False,
            canonical={},
            template_payload=None,
            errors=[
                ValidationResult(
                    rule_id="input.type",
                    severity="blocked",
                    passed=False,
                    message="input must be a dict",
                )
            ],
        )

    # Work on a shallow copy to avoid mutating the caller's data
    working = dict(data)

    normalizations: list[FieldProvenance] = []
    computed_fields: list[str] = []
    unknown_fields: list[UnknownField] = []
    errors: list[ValidationResult] = []
    warnings: list[ValidationResult] = []

    # Stage 0: Pre-process structural variations
    working = _preprocess_structure(working, normalizations)

    # Stage 1: Resolve field names
    working = _resolve_field_names(working, normalizations)

    # Stage 2: Coerce types
    working = _coerce_types(working, normalizations)

    # Stage 3: Compute missing values
    working = _compute_missing(working, normalizations, computed_fields)

    # Stage 4: Classify unknown fields
    working = _classify_unknown_fields(working, unknown_fields)

    # Stage 5: Validate semantics
    _validate_semantics(working, errors, warnings)

    # Stage 6: Build canonical
    canonical = _build_canonical(working)

    # Determine status
    has_blocked = any(e.severity == "blocked" for e in errors)
    has_errors = any(e.severity == "error" for e in errors)
    has_warnings = bool(warnings)

    if has_blocked:
        status: Literal["ready", "ready_with_warnings", "blocked"] = "blocked"
    elif has_errors or has_warnings:
        status = "ready_with_warnings"
    else:
        status = "ready"

    render_ready = not has_blocked

    # Stage 7: Reshape for template — only when safe to render
    # template_payload is None when blocked to prevent accidental downstream use
    template_payload = canonical.to_template_shape() if render_ready else None

    # Filter normalizations: only alias/computed/default (not exact matches)
    meaningful_normalizations = [n for n in normalizations if n.source != "exact"]

    return IngestionReport(
        status=status,
        render_ready=render_ready,
        canonical=canonical.to_dict(),
        template_payload=template_payload,
        errors=errors,
        warnings=warnings,
        normalizations=meaningful_normalizations,
        computed_fields=computed_fields,
        unknown_fields=unknown_fields,
    )
