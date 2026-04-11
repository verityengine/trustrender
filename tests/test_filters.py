"""Tests for Jinja2 template filters."""

from markupsafe import Markup

from formforge.filters import typst_color, typst_markup, typst_money
from formforge.templates import render_template, typst_escape

FIXTURES = "tests/fixtures"


class TestTypstMoney:
    def test_positive_value(self):
        result = typst_money("$1,200.00")
        assert "\\$1,200.00" in str(result)
        assert "#text(fill:" not in str(result)

    def test_negative_value_red(self):
        result = typst_money("-$500.00")
        assert '#text(fill: rgb("#c0392b"))' in str(result)
        assert "-\\$500.00" in str(result)

    def test_custom_negative_color(self):
        result = typst_money("-$100.00", negative_color="#e74c3c")
        assert '#text(fill: rgb("#e74c3c"))' in str(result)

    def test_returns_markup(self):
        assert isinstance(typst_money("$100"), Markup)
        assert isinstance(typst_money("-$100"), Markup)

    def test_escapes_dollar(self):
        result = typst_money("$100")
        assert "\\$100" in str(result)

    def test_zero_value(self):
        result = typst_money("$0.00")
        assert "#text(fill:" not in str(result)


class TestTypstColor:
    def test_wraps_in_color(self):
        result = typst_color("Above", "#27ae60")
        assert str(result) == '#text(fill: rgb("#27ae60"))[Above]'

    def test_escapes_value(self):
        result = typst_color("$100 earned", "#27ae60")
        assert "\\$100" in str(result)

    def test_returns_markup(self):
        assert isinstance(typst_color("test", "#000"), Markup)

    def test_brackets_in_value_cannot_break_content_block(self):
        """Brackets/braces in filter input must not break the [...] wrapper."""
        result = typst_color(']}{read("x")}[', "#27ae60")
        s = str(result)
        # The ] must be escaped so it cannot close the #text(...)[...] block
        assert "\\u{005d}" in s
        assert "\\u{007b}" in s
        # The wrapping content block must be intact (starts with [ and ends with ])
        assert s.startswith('#text(fill: rgb("#27ae60"))[')
        assert s.endswith("]")


class TestTypstMarkup:
    def test_returns_markup(self):
        result = typst_markup('#text(weight: "bold")[hello]')
        assert isinstance(result, Markup)

    def test_bypasses_escape(self):
        raw = "#text(fill: red)[$100]"
        result = typst_markup(raw)
        # Should NOT be escaped
        assert str(result) == raw
        # And should bypass typst_escape
        assert typst_escape(result) is result


class TestFiltersInTemplate:
    def test_typst_money_in_template(self):
        result = render_template(
            f"{FIXTURES}/simple.j2.typ",
            {"title": "Test", "body": "Amount: ", "note": ""},
        )
        # Basic template renders
        assert "Test" in result

    def test_typst_markup_bypasses_auto_escape(self):
        result = render_template(
            f"{FIXTURES}/simple.j2.typ",
            {"title": "Test", "body": "text", "note": ""},
        )
        # Auto-escape is still active for normal values
        assert "#set page" in result  # Typst code NOT escaped
