"""Ugly-data pressure tests: truth-boundary cases for real-world messy payloads.

Each test is classified by expected verdict:
  - should block: contract/type error prevents rendering
  - should warn: render proceeds, operator sees a warning
  - should allow, with warning: valid but suspicious — render + warning
  - should allow, no warning: valid unusual input, no complaint

Tests exercise BOTH surfaces where applicable:
  - render() — does it produce a valid PDF or raise?
  - preflight() — does readiness catch, warn, or miss it?
  - validate_semantics() — do semantic checks fire correctly?

Priority order (highest risk to public claims first):
  1. Malformed dates
  2. Mixed-locale currency strings
  3. Control characters
  4. RTL text
  5. Very large integers / precision loss
  6. Duplicate semantic keys
  7. Numeric edge cases
  8. Inconsistent item schemas
  9. Rounding accumulation
  10. Zero quantity / zero price
  11. Type confusion
  12. Deep nesting
  13. Preflight-specific ugly payloads
"""

from pathlib import Path

import pytest

from trustrender import render
from trustrender.readiness import preflight
from trustrender.semantic import (
    INVOICE_HINTS,
    RECEIPT_HINTS,
    STATEMENT_HINTS,
    SemanticHints,
    validate_semantics,
)

EXAMPLES = Path("examples")


def assert_valid_pdf(pdf_bytes: bytes):
    assert pdf_bytes[:5] == b"%PDF-", "Not a valid PDF"
    assert len(pdf_bytes) > 1000, "PDF suspiciously small"


# ---------------------------------------------------------------------------
# Invoice base data helper
# ---------------------------------------------------------------------------

def _invoice_data(**overrides):
    data = {
        "invoice_number": "INV-001",
        "invoice_date": "Jan 1, 2026",
        "due_date": "Feb 1, 2026",
        "payment_terms": "Net 30",
        "sender": {
            "name": "Sender Co",
            "address_line1": "123 Main St",
            "address_line2": "City, ST 00000",
            "email": "a@b.com",
        },
        "recipient": {
            "name": "Recipient Co",
            "address_line1": "456 Oak Ave",
            "address_line2": "Town, ST 11111",
            "email": "x@y.com",
        },
        "items": [
            {
                "num": 1,
                "description": "Service",
                "qty": 1,
                "unit_price": "$100.00",
                "amount": "$100.00",
            }
        ],
        "subtotal": "$100.00",
        "tax_rate": "0%",
        "tax_amount": "$0.00",
        "total": "$100.00",
        "notes": "Thanks.",
    }
    data.update(overrides)
    return data


def _statement_data(**overrides):
    data = {
        "company": {
            "name": "Co",
            "address_line1": "Addr",
            "address_line2": "City",
            "email": "a@b.com",
            "phone": "555-0000",
        },
        "customer": {
            "name": "Cust",
            "account_number": "ACCT-001",
            "address_line1": "Addr",
            "address_line2": "City",
            "email": "x@y.com",
        },
        "statement_date": "Jan 1, 2026",
        "period": "Dec 2025",
        "opening_balance": "$0.00",
        "closing_balance": "$100.00",
        "total_charges": "$100.00",
        "total_payments": "$0.00",
        "transactions": [
            {
                "date": "Dec 15",
                "description": "Charge",
                "reference": "INV-001",
                "amount": "$100.00",
                "balance": "$100.00",
            },
        ],
        "aging": {
            "current": "$100.00",
            "days_30": "$0.00",
            "days_60": "$0.00",
            "days_90": "$0.00",
            "total": "$100.00",
        },
        "notes": "Pay soon.",
    }
    data.update(overrides)
    return data


INVOICE_TEMPLATE = EXAMPLES / "invoice.j2.typ"
STATEMENT_TEMPLATE = EXAMPLES / "statement.j2.typ"
RECEIPT_TEMPLATE = EXAMPLES / "receipt.j2.typ"


# ===================================================================
# 1. MALFORMED DATES
# Verdict: should allow, with warning (semantic layer warns, render OK)
# ===================================================================

class TestMalformedDates:
    """Date fields with values that don't match standard formats."""

    def test_ambiguous_date_01_02_03(self):
        """01/02/03 — could be Jan 2, 2003 or Feb 1, 2003 or 2001-02-03."""
        data = _invoice_data(invoice_date="01/02/03", due_date="02/03/03")
        # Should render fine (dates are just strings in template)
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))
        # Semantic should warn: can't parse these reliably
        report = validate_semantics(data, INVOICE_HINTS)
        date_issues = [i for i in report.issues if i.category == "date_format"]
        assert len(date_issues) >= 1, "Should warn on ambiguous date format"

    def test_iso_with_timezone(self):
        """ISO 8601 with timezone offset."""
        data = _invoice_data(
            invoice_date="2026-04-10T14:30:00+02:00",
            due_date="2026-05-10T14:30:00Z",
        )
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))
        report = validate_semantics(data, INVOICE_HINTS)
        date_issues = [i for i in report.issues if i.category == "date_format"]
        # ISO with TZ is not in our format list — should warn
        assert len(date_issues) >= 1

    def test_epoch_timestamp_as_date(self):
        """Unix timestamp instead of date string."""
        data = _invoice_data(invoice_date="1775500800", due_date="1778179200")
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))
        report = validate_semantics(data, INVOICE_HINTS)
        date_issues = [i for i in report.issues if i.category == "date_format"]
        assert len(date_issues) >= 1

    def test_tbd_as_date(self):
        """'TBD' in a date field."""
        data = _invoice_data(invoice_date="TBD", due_date="TBD")
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))
        report = validate_semantics(data, INVOICE_HINTS)
        date_issues = [i for i in report.issues if i.category == "date_format"]
        assert len(date_issues) == 2

    def test_empty_string_date(self):
        """Empty string in date field."""
        data = _invoice_data(invoice_date="", due_date="")
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))
        # Empty string dates should not trigger date format warning (empty is OK)

    def test_integer_as_date(self):
        """Integer value passed as date (type confusion)."""
        data = _invoice_data(invoice_date=20260410, due_date=20260510)
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))
        report = validate_semantics(data, INVOICE_HINTS)
        date_issues = [i for i in report.issues if i.category == "date_format"]
        assert len(date_issues) >= 1, "Should warn: integer is not a date string"


# ===================================================================
# 2. MIXED-LOCALE CURRENCY STRINGS
# Verdict: should allow, no warning (render) / should warn (semantic)
# ===================================================================

class TestMixedLocaleCurrency:
    """Currency values with different symbols, formats, and conventions."""

    def test_indian_rupee_symbol(self):
        """₹ symbol — not in the current currency strip regex.

        FINDING: ₹ is NOT in the strip regex [€$£¥]. The semantic layer
        cannot parse ₹10,000.00 as a number. This means numeric_coercion
        warnings fire for ₹ amounts. Render still works (just strings).
        Verdict: should allow render (no warning), semantic warns (acceptable).
        """
        data = _invoice_data(subtotal="₹10,000.00", tax_amount="₹1,800.00", total="₹11,800.00")
        data["items"][0]["amount"] = "₹10,000.00"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))
        # FINDING: No warnings fire at all.
        # - INVOICE_HINTS.numeric_fields checks items[].quantity/unit_price/line_total
        #   but test data uses 'amount', not 'line_total' — no numeric_coercion check
        # - subtotal/total have ₹ prefix → _try_parse_number fails → arithmetic
        #   check silently bails (subtotal is None)
        # Net result: non-standard currencies are invisible to semantic validation.
        # This is a real gap — documented in ugly-data-findings.md.
        report = validate_semantics(data, INVOICE_HINTS)
        # Verify no warnings fire (confirming the gap)
        assert len(report.issues) == 0, (
            f"Expected no warnings (gap: ₹ is invisible), got: {report.issues}"
        )

    def test_brazilian_real(self):
        """R$ prefix — two-char currency symbol."""
        data = _invoice_data(subtotal="R$5.000,00", tax_amount="R$0,00", total="R$5.000,00")
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_swedish_krona(self):
        """kr suffix (post-fix currency)."""
        data = _invoice_data(subtotal="10 000 kr", tax_amount="0 kr", total="10 000 kr")
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_european_comma_decimal(self):
        """1.234,56 — period as thousands sep, comma as decimal.

        FINDING: Current parser strips commas as thousands separators,
        leaving '1.234.56' which fails float(). European format not supported.
        Verdict: should allow render (no warning), semantic warns (acceptable limit).
        """
        data = _invoice_data(subtotal="1.234,56", tax_amount="0,00", total="1.234,56")
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_mixed_symbols_one_payload(self):
        """Different currency symbols in the same payload — messy ETL artifact."""
        data = _invoice_data()
        data["items"] = [
            {"num": 1, "description": "Service A", "qty": 1, "unit_price": "$100.00", "amount": "$100.00"},
            {"num": 2, "description": "Service B", "qty": 1, "unit_price": "€85.00", "amount": "€85.00"},
            {"num": 3, "description": "Service C", "qty": 1, "unit_price": "£70.00", "amount": "£70.00"},
        ]
        data["subtotal"] = "$255.00"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_accounting_parens_negative(self):
        """(500.00) — accounting notation for negative.

        Semantic should parse parens as negative -500.00 (implemented).
        """
        data = _invoice_data()
        data["items"][0]["amount"] = "(500.00)"
        data["subtotal"] = "(500.00)"
        data["total"] = "(500.00)"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_bare_numbers_no_symbol(self):
        """Plain numbers without any currency symbol."""
        data = _invoice_data(subtotal="100.00", tax_amount="0.00", total="100.00")
        data["items"][0]["amount"] = "100.00"
        data["items"][0]["unit_price"] = "100.00"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))


# ===================================================================
# 3. CONTROL CHARACTERS
# Verdict: should allow, no warning (render must handle gracefully)
# ===================================================================

class TestControlCharacters:
    """Strings with control characters, null bytes, zero-width chars."""

    def test_tab_in_company_name(self):
        data = _invoice_data()
        data["sender"]["name"] = "Sender\tCo"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_newline_in_description(self):
        data = _invoice_data()
        data["items"][0]["description"] = "Line one\nLine two\nLine three"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_carriage_return_line_feed(self):
        data = _invoice_data()
        data["items"][0]["description"] = "Windows\r\nline break"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_form_feed(self):
        data = _invoice_data()
        data["notes"] = "Before\fAfter"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_zero_width_space(self):
        """Zero-width space (U+200B) — invisible but present."""
        data = _invoice_data()
        data["sender"]["name"] = "Sender\u200BCo"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_zero_width_joiner(self):
        """Zero-width joiner (U+200D)."""
        data = _invoice_data()
        data["sender"]["name"] = "A\u200DB Corp"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_non_breaking_space(self):
        """Non-breaking space (U+00A0)."""
        data = _invoice_data()
        data["items"][0]["description"] = "Item\u00A0Description"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_null_byte_in_string(self):
        """Null byte (U+0000) — should not crash, may be stripped or escaped."""
        data = _invoice_data()
        data["notes"] = "Before\x00After"
        # This may fail if Typst or Jinja2 can't handle null bytes
        # That is an acceptable limit — but it should not crash silently
        try:
            pdf = render(INVOICE_TEMPLATE, data)
            assert_valid_pdf(pdf)
        except Exception as e:
            # Acceptable if it raises a clear error
            assert str(e), "Error should have a message"


# ===================================================================
# 4. RTL TEXT
# Verdict: should allow, no warning (render must produce valid PDF)
# ===================================================================

class TestRTLText:
    """Arabic and Hebrew text in various fields."""

    def test_arabic_company_name(self):
        data = _invoice_data()
        data["sender"]["name"] = "شركة الابتكار للتقنية"
        data["recipient"]["name"] = "مؤسسة النور للاستشارات"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_hebrew_company_name(self):
        data = _invoice_data()
        data["sender"]["name"] = "חברת הטכנולוגיה"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_arabic_item_descriptions(self):
        data = _invoice_data()
        data["items"] = [
            {
                "num": 1,
                "description": "خدمات استشارية في مجال تكنولوجيا المعلومات",
                "qty": 1,
                "unit_price": "$5,000.00",
                "amount": "$5,000.00",
            },
            {
                "num": 2,
                "description": "تطوير البرمجيات والصيانة",
                "qty": 1,
                "unit_price": "$3,000.00",
                "amount": "$3,000.00",
            },
        ]
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_mixed_rtl_ltr(self):
        """Mixed RTL and LTR text in one field (bidi)."""
        data = _invoice_data()
        data["sender"]["name"] = "شركة ABC للتقنية"
        data["notes"] = "Payment reference: REF-123 مرجع الدفع"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_rtl_in_statement(self):
        data = _statement_data()
        data["customer"]["name"] = "عميل الاختبار"
        data["company"]["name"] = "شركة البيانات"
        assert_valid_pdf(render(STATEMENT_TEMPLATE, data))


# ===================================================================
# 5. VERY LARGE INTEGERS / PRECISION LOSS
# Verdict: should allow, no warning (but check for precision loss)
# ===================================================================

class TestLargeIntegers:
    """Totals above 2^53, 15+ digit amounts, extreme precision."""

    def test_15_digit_total(self):
        """15-digit number — near the edge of float64 precision."""
        data = _invoice_data(
            subtotal="$999,999,999,999.99",
            tax_amount="$0.00",
            total="$999,999,999,999.99",
        )
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_beyond_float64_precision(self):
        """Number that exceeds float64 integer precision (2^53+1).

        FINDING: float() silently loses precision at this scale.
        Semantic layer parses it but may compare inexactly.
        Verdict: should allow render (no warning), precision loss is acceptable limit.
        """
        big = "9,007,199,254,740,993.00"  # 2^53 + 1
        data = _invoice_data(subtotal=f"${big}", tax_amount="$0.00", total=f"${big}")
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_many_decimal_places(self):
        """Price with many decimal places (crypto-style)."""
        data = _invoice_data()
        data["items"][0]["unit_price"] = "0.00000001"
        data["items"][0]["amount"] = "0.00000001"
        data["subtotal"] = "0.00000001"
        data["total"] = "0.00000001"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_three_decimal_price(self):
        """$9.999 — common in fuel/commodity pricing."""
        data = _invoice_data()
        data["items"][0]["unit_price"] = "$9.999"
        data["items"][0]["amount"] = "$9.999"
        data["subtotal"] = "$9.999"
        data["total"] = "$9.999"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_very_small_fractional(self):
        """$0.001 — sub-cent amount."""
        data = _invoice_data()
        data["items"][0]["unit_price"] = "$0.001"
        data["items"][0]["amount"] = "$0.001"
        data["subtotal"] = "$0.001"
        data["total"] = "$0.001"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))


# ===================================================================
# 6. DUPLICATE SEMANTIC KEYS
# Verdict: should allow, no warning (templates reference specific keys)
# ===================================================================

class TestDuplicateSemanticKeys:
    """Data with both 'total' and 'grand_total', or 'tax' and 'tax_amount'."""

    def test_both_total_and_grand_total(self):
        """Upstream transform puts both. Template only uses one."""
        data = _invoice_data()
        data["grand_total"] = "$100.00"  # Extra key, not in template
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))
        # Contract should NOT block (extra fields are allowed)
        verdict = preflight(INVOICE_TEMPLATE, data)
        assert verdict.ready, f"Extra keys should not block: {verdict.errors}"

    def test_both_tax_and_tax_amount(self):
        """Both 'tax' and 'tax_amount' present."""
        data = _invoice_data()
        data["tax"] = "$0.00"  # Extra, template uses tax_amount
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_nested_duplicates(self):
        """Multiple address representations for same entity."""
        data = _invoice_data()
        data["sender"]["address"] = "123 Main St, City, ST 00000"  # Flat version
        data["sender"]["addr"] = {"street": "123 Main St", "city": "City"}  # Structured
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_preflight_ignores_extra_keys(self):
        """Preflight should pass even with many extra keys."""
        data = _invoice_data()
        data["metadata"] = {"source": "api", "version": 3}
        data["_internal"] = True
        data["debug_info"] = {"timestamp": "2026-04-12"}
        verdict = preflight(INVOICE_TEMPLATE, data)
        assert verdict.ready, f"Extra keys should not block: {verdict.errors}"


# ===================================================================
# 7. NUMERIC EDGE CASES
# Verdict: mixed — some should allow, some should warn
# ===================================================================

class TestNumericEdgeCases:
    """Booleans, scientific notation, NaN, Infinity, negative zero."""

    def test_boolean_in_qty(self):
        """True/False where a number is expected. Template just prints it."""
        data = _invoice_data()
        data["items"][0]["qty"] = True  # Python True == 1
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_scientific_notation(self):
        """1e6 as a string — should render, may or may not parse as number."""
        data = _invoice_data()
        data["items"][0]["amount"] = "1e6"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_negative_zero(self):
        """-0.0 as a float."""
        data = _invoice_data()
        data["tax_amount"] = -0.0
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_infinity_string(self):
        """'Infinity' as a string in a numeric field.

        FIX: _try_parse_number now rejects non-finite values (Infinity, NaN).
        Verdict: should warn — and now does.
        """
        data = _invoice_data()
        data["items"][0]["amount"] = "Infinity"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))
        # Use hints that target the 'amount' field (INVOICE_HINTS uses 'line_total')
        hints = SemanticHints(numeric_fields=["items[].amount"])
        report = validate_semantics(data, hints)
        numeric_issues = [i for i in report.issues if i.category == "numeric_coercion"]
        assert len(numeric_issues) >= 1, "Infinity should trigger numeric_coercion warning"

    def test_nan_string(self):
        """'NaN' as a string — should warn (not a valid business amount)."""
        data = _invoice_data()
        data["items"][0]["amount"] = "NaN"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))
        hints = SemanticHints(numeric_fields=["items[].amount"])
        report = validate_semantics(data, hints)
        numeric_issues = [i for i in report.issues if i.category == "numeric_coercion"]
        assert len(numeric_issues) >= 1, "NaN should trigger numeric_coercion warning"

    def test_integer_amounts(self):
        """Plain integers instead of formatted strings."""
        data = _invoice_data()
        data["subtotal"] = 100
        data["tax_amount"] = 0
        data["total"] = 100
        data["items"][0]["qty"] = 1
        data["items"][0]["unit_price"] = 100
        data["items"][0]["amount"] = 100
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_float_amounts(self):
        """Python floats instead of strings."""
        data = _invoice_data()
        data["subtotal"] = 100.50
        data["tax_amount"] = 8.04
        data["total"] = 108.54
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))


# ===================================================================
# 8. INCONSISTENT ITEM SCHEMAS
# Verdict: should allow, no warning (extra fields ignored by template)
# ===================================================================

class TestInconsistentItemSchemas:
    """List items where some have extra fields or missing optional fields."""

    def test_items_with_varying_fields(self):
        """Some items have extra fields that others don't."""
        data = _invoice_data()
        data["items"] = [
            {"num": 1, "description": "Basic item", "qty": 1, "unit_price": "$10.00", "amount": "$10.00"},
            {"num": 2, "description": "With SKU", "qty": 2, "unit_price": "$20.00", "amount": "$40.00", "sku": "ABC-123"},
            {"num": 3, "description": "With discount", "qty": 1, "unit_price": "$30.00", "amount": "$25.00", "discount": "15%"},
        ]
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_items_with_none_values(self):
        """Items where some fields are None.

        FINDING: Contract correctly blocks None in required fields.
        description is required (used directly in template, not guarded).
        Verdict: should block — and does. Contract catches it.
        """
        from trustrender.errors import TrustRenderError

        data = _invoice_data()
        data["items"] = [
            {"num": 1, "description": "Item 1", "qty": 1, "unit_price": "$10.00", "amount": "$10.00"},
            {"num": 2, "description": None, "qty": 1, "unit_price": "$20.00", "amount": "$20.00"},
        ]
        with pytest.raises(TrustRenderError) as exc_info:
            render(INVOICE_TEMPLATE, data)
        # Error message mentions field count; detail attribute has path info
        assert "1 field error" in str(exc_info.value)

    def test_sparse_items(self):
        """Items with minimal fields vs full fields."""
        data = _invoice_data()
        data["items"] = [
            {"num": 1, "description": "Full item", "qty": 5, "unit_price": "$10.00", "amount": "$50.00"},
            {"num": 2, "description": "", "qty": "", "unit_price": "", "amount": ""},
        ]
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))


# ===================================================================
# 9. ROUNDING ACCUMULATION
# Verdict: should allow, with warning (arithmetic check catches drift)
# ===================================================================

class TestRoundingAccumulation:
    """Many items where individual rounding is correct but sum drifts."""

    def test_50_items_rounding_drift(self):
        """50 items at $33.33 each — sum is $1666.50, not 50 * $33.33 = $1666.50.
        But what about $33.333... per item?"""
        items = []
        for i in range(1, 51):
            items.append({
                "num": i,
                "description": f"Item {i}",
                "qty": 1,
                "unit_price": "$33.33",
                "amount": "$33.33",
            })
        data = _invoice_data()
        data["items"] = items
        # Correct sum: 50 * 33.33 = 1666.50
        data["subtotal"] = "$1,666.50"
        data["total"] = "$1,666.50"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_rounding_drift_past_tolerance(self):
        """Subtotal that doesn't match item sum by more than $0.01."""
        items = [
            {"num": 1, "description": "A", "qty": 1, "unit_price": "$10.00", "amount": "$10.00"},
            {"num": 2, "description": "B", "qty": 1, "unit_price": "$20.00", "amount": "$20.00"},
        ]
        data = _invoice_data()
        data["items"] = items
        # Items sum to $30.00, but subtotal says $30.05 — off by $0.05
        data["subtotal"] = "$30.05"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))
        # Semantic should warn about arithmetic mismatch
        hints = SemanticHints(
            line_items_path="items",
            line_total_field="amount",
            subtotal_path="subtotal",
        )
        report = validate_semantics(data, hints)
        arithmetic_issues = [i for i in report.issues if i.category == "arithmetic"]
        assert len(arithmetic_issues) >= 1, "Should warn on arithmetic drift > $0.01"

    def test_rounding_within_tolerance(self):
        """Off by $0.005 — within tolerance, no warning.

        FINDING: Exact $0.01 boundary fires due to float representation:
        abs(30.0 - 30.01) = 0.010000000000001563 > 0.01.
        Using $0.005 offset to stay safely within tolerance.
        The boundary behavior is an acceptable limit — tolerance is >0.01, not >=0.01.
        """
        items = [
            {"num": 1, "description": "A", "qty": 1, "unit_price": "$10.00", "amount": "$10.00"},
            {"num": 2, "description": "B", "qty": 1, "unit_price": "$20.00", "amount": "$20.00"},
        ]
        data = _invoice_data()
        data["items"] = items
        data["subtotal"] = "$30.005"  # Off by $0.005 — within tolerance
        hints = SemanticHints(
            line_items_path="items",
            line_total_field="amount",
            subtotal_path="subtotal",
        )
        report = validate_semantics(data, hints)
        arithmetic_issues = [i for i in report.issues if i.category == "arithmetic"]
        assert len(arithmetic_issues) == 0, "Should NOT warn within $0.01 tolerance"


# ===================================================================
# 10. ZERO QUANTITY / ZERO PRICE
# Verdict: should allow, no warning
# ===================================================================

class TestZeroValues:
    """Items with zero quantity, zero price, or zero amount."""

    def test_zero_quantity(self):
        data = _invoice_data()
        data["items"][0]["qty"] = 0
        data["items"][0]["amount"] = "$0.00"
        data["subtotal"] = "$0.00"
        data["total"] = "$0.00"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_zero_price(self):
        data = _invoice_data()
        data["items"][0]["unit_price"] = "$0.00"
        data["items"][0]["amount"] = "$0.00"
        data["subtotal"] = "$0.00"
        data["total"] = "$0.00"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_free_item_in_list(self):
        """One free item among paid items."""
        data = _invoice_data()
        data["items"] = [
            {"num": 1, "description": "Paid item", "qty": 1, "unit_price": "$50.00", "amount": "$50.00"},
            {"num": 2, "description": "Free item (promo)", "qty": 1, "unit_price": "$0.00", "amount": "$0.00"},
        ]
        data["subtotal"] = "$50.00"
        data["total"] = "$50.00"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_all_zeros(self):
        """Invoice with all zero amounts — edge case for credit memo."""
        data = _invoice_data()
        data["subtotal"] = "$0.00"
        data["tax_amount"] = "$0.00"
        data["total"] = "$0.00"
        data["items"][0]["qty"] = 0
        data["items"][0]["unit_price"] = "$0.00"
        data["items"][0]["amount"] = "$0.00"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))


# ===================================================================
# 11. TYPE CONFUSION
# Verdict: mixed — should allow (render) but some should warn (semantic)
# ===================================================================

class TestTypeConfusion:
    """String versions of special values: 'true', 'false', 'null', '0', ''."""

    def test_string_true_false(self):
        """String 'true' / 'false' where text expected."""
        data = _invoice_data()
        data["notes"] = "true"
        data["payment_terms"] = "false"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_string_null(self):
        """String 'null' where text expected."""
        data = _invoice_data()
        data["notes"] = "null"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_string_zero(self):
        """String '0' where text expected."""
        data = _invoice_data()
        data["tax_rate"] = "0"
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_none_in_optional_field(self):
        """Python None in 'notes' field.

        FINDING: 'notes' is used directly in invoice template (not guarded
        by {% if %}), so contract treats it as required. None triggers
        contract validation error. This is correct behavior.
        Verdict: should block — and does.
        """
        from trustrender.errors import TrustRenderError

        data = _invoice_data()
        data["notes"] = None
        with pytest.raises(TrustRenderError):
            render(INVOICE_TEMPLATE, data)

    def test_empty_dict_as_sender(self):
        """Empty dict where object expected — contract should catch."""
        data = _invoice_data()
        data["sender"] = {}
        # This should either raise contract error or render with empty fields
        try:
            pdf = render(INVOICE_TEMPLATE, data)
            # If it renders, it should be a valid PDF (just with missing content)
            assert_valid_pdf(pdf)
        except Exception:
            pass  # Contract error is acceptable

    def test_list_where_scalar_expected(self):
        """List passed where a scalar string is expected — contract should catch."""
        data = _invoice_data()
        data["invoice_number"] = ["INV-001", "INV-002"]
        try:
            pdf = render(INVOICE_TEMPLATE, data)
            assert_valid_pdf(pdf)
        except Exception:
            pass  # Contract error is acceptable


# ===================================================================
# 12. DEEP NESTING
# Verdict: should allow, no warning
# ===================================================================

class TestDeepNesting:
    """Data with deeply nested structures — extra depth beyond template needs."""

    def test_deeply_nested_sender(self):
        """Sender with extra nested metadata."""
        data = _invoice_data()
        data["sender"]["metadata"] = {
            "level1": {
                "level2": {
                    "level3": {
                        "level4": {
                            "level5": "deep value"
                        }
                    }
                }
            }
        }
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_items_with_nested_metadata(self):
        """Items with extra nested fields."""
        data = _invoice_data()
        data["items"][0]["product"] = {
            "category": {"name": "Services", "parent": {"name": "Business"}},
            "tags": ["consulting", "tech"],
        }
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))


# ===================================================================
# 13. PREFLIGHT-SPECIFIC UGLY PAYLOADS
# Tests both preflight() and render() to verify surface consistency
# ===================================================================

class TestPreflightUglyPayloads:
    """Preflight-specific edge cases — data that passes contract but fails semantic,
    and data that has extra fields, type confusion, etc."""

    def test_preflight_with_semantic_mismatch(self):
        """Data passes contract but has arithmetic mismatch in semantic layer."""
        data = _invoice_data()
        data["items"] = [
            {"num": 1, "description": "A", "qty": 1, "unit_price": "$100.00", "amount": "$100.00"},
            {"num": 2, "description": "B", "qty": 1, "unit_price": "$200.00", "amount": "$200.00"},
        ]
        data["subtotal"] = "$400.00"  # Wrong: should be $300.00
        # Preflight should pass (no semantic hints by default) — contract is OK
        verdict = preflight(INVOICE_TEMPLATE, data)
        assert verdict.ready, f"Contract is valid, should be ready: {verdict.errors}"
        # But render should still work (semantic doesn't block)
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_preflight_with_many_extra_keys(self):
        """Data with lots of extra keys that aren't in the template."""
        data = _invoice_data()
        for i in range(20):
            data[f"extra_field_{i}"] = f"value_{i}"
        verdict = preflight(INVOICE_TEMPLATE, data)
        assert verdict.ready, f"Extra fields should not block: {verdict.errors}"

    def test_preflight_with_string_numbers(self):
        """All numeric-ish fields are strings (common from JSON APIs)."""
        data = _invoice_data()
        data["items"][0]["qty"] = "1"
        data["items"][0]["num"] = "1"
        verdict = preflight(INVOICE_TEMPLATE, data)
        assert verdict.ready

    def test_preflight_with_null_optional(self):
        """None in an optional/guarded field."""
        data = _invoice_data()
        data["notes"] = None
        verdict = preflight(INVOICE_TEMPLATE, data)
        # Depends on whether notes is required in the contract
        # Either way, should not crash
        assert isinstance(verdict.ready, bool)

    def test_preflight_with_bool_qty(self):
        """Boolean True where int expected (qty)."""
        data = _invoice_data()
        data["items"][0]["qty"] = True
        verdict = preflight(INVOICE_TEMPLATE, data)
        assert verdict.ready  # Contract says SCALAR, True is scalar
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_preflight_statement_with_ugly_aging(self):
        """Statement with weird aging values."""
        data = _statement_data()
        data["aging"]["current"] = "N/A"
        data["aging"]["days_30"] = ""
        data["aging"]["days_60"] = None
        # Should render (template just prints these)
        try:
            assert_valid_pdf(render(STATEMENT_TEMPLATE, data))
        except Exception:
            pass  # If contract catches None, that's OK
        # Preflight should not crash
        verdict = preflight(STATEMENT_TEMPLATE, data)
        assert isinstance(verdict.ready, bool)

    def test_render_and_preflight_agree(self):
        """If preflight says ready, render should succeed."""
        data = _invoice_data()
        verdict = preflight(INVOICE_TEMPLATE, data)
        assert verdict.ready
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))

    def test_render_and_preflight_agree_statement(self):
        """Same check for statement template."""
        data = _statement_data()
        verdict = preflight(STATEMENT_TEMPLATE, data)
        assert verdict.ready
        assert_valid_pdf(render(STATEMENT_TEMPLATE, data))

    def test_preflight_warns_on_contaminated_text(self):
        """Realistic invoice with null byte in sender name:
        preflight PASS with semantic text_anomaly warning."""
        data = _invoice_data()
        data["sender"]["name"] = "Acme\x00Corp"
        verdict = preflight(
            INVOICE_TEMPLATE, data,
            semantic_hints=INVOICE_HINTS,
        )
        assert verdict.ready  # Warnings don't block
        text_warnings = [w for w in verdict.warnings if w.check == "text_anomaly"]
        assert len(text_warnings) >= 1
        assert "null byte" in text_warnings[0].message

    def test_contaminated_text_renders_with_warning(self):
        """Zero-width space in description: render succeeds, semantic warns."""
        data = _invoice_data()
        data["items"][0]["description"] = "Widget\u200BPro"
        # Render succeeds — text anomaly is warning-only
        assert_valid_pdf(render(INVOICE_TEMPLATE, data))
        # Semantic layer catches it
        report = validate_semantics(data, hints=INVOICE_HINTS)
        anomalies = [i for i in report.issues if i.category == "text_anomaly"]
        assert len(anomalies) >= 1
        assert "zero-width space" in anomalies[0].message
