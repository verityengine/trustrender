"""Tests for Jinja2 template preprocessing and auto-escaping."""

from formforge.templates import render_template, typst_escape

FIXTURES = "tests/fixtures"


class TestTypstEscape:
    def test_escapes_dollar(self):
        assert typst_escape("$100") == "\\$100"

    def test_escapes_hash(self):
        assert typst_escape("#tag") == "\\#tag"

    def test_escapes_at(self):
        assert typst_escape("@ref") == "\\@ref"

    def test_escapes_backslash(self):
        assert typst_escape("a\\b") == "a\\\\b"

    def test_escapes_less_than(self):
        assert typst_escape("<4") == "\\u{003c}4"

    def test_escapes_backtick(self):
        assert typst_escape("`code`") == "\\u{0060}code\\u{0060}"

    def test_escapes_tilde(self):
        assert typst_escape("a~b") == "a\\~b"

    def test_escapes_open_brace(self):
        assert typst_escape("{code}") == "\\u{007b}code\\u{007d}"

    def test_escapes_close_brace(self):
        assert typst_escape("a}b") == "a\\u{007d}b"

    def test_escapes_open_bracket(self):
        assert typst_escape("[content]") == "\\u{005b}content\\u{005d}"

    def test_escapes_close_bracket(self):
        assert typst_escape("a]b") == "a\\u{005d}b"

    def test_escapes_code_injection_via_braces(self):
        """Curly braces must not allow code mode entry."""
        assert typst_escape('{read("/etc/passwd")}') == '\\u{007b}read("/etc/passwd")\\u{007d}'

    def test_escapes_content_block_breakout(self):
        """Close bracket must not break out of content blocks."""
        assert typst_escape("]{evil}[") == "\\u{005d}\\u{007b}evil\\u{007d}\\u{005b}"

    def test_escapes_all_brackets_and_braces(self):
        """All four bracket/brace characters escaped in one string."""
        assert typst_escape("[{x}]") == "\\u{005b}\\u{007b}x\\u{007d}\\u{005d}"

    def test_escapes_all_together(self):
        assert typst_escape("$100 #tag @ref a\\b {x} [y]") == (
            "\\$100 \\#tag \\@ref a\\\\b \\u{007b}x\\u{007d} \\u{005b}y\\u{005d}"
        )

    def test_passthrough_non_string(self):
        assert typst_escape(42) == 42
        assert typst_escape(None) is None
        assert typst_escape([1, 2]) == [1, 2]

    def test_passthrough_markup(self):
        from markupsafe import Markup

        m = Markup("#text(fill: red)[hello]")
        assert typst_escape(m) is m

    def test_empty_string(self):
        assert typst_escape("") == ""

    def test_no_special_chars(self):
        assert typst_escape("hello world") == "hello world"


class TestRenderTemplate:
    def test_renders_simple_template(self):
        result = render_template(
            f"{FIXTURES}/simple.j2.typ",
            {"title": "Hello", "body": "World", "note": ""},
        )
        assert "= Hello" in result
        assert "World" in result

    def test_auto_escapes_dollar_in_data(self):
        result = render_template(
            f"{FIXTURES}/simple.j2.typ",
            {"title": "Invoice $500", "body": "Pay $100", "note": ""},
        )
        assert "\\$500" in result
        assert "\\$100" in result
        # Typst markup characters should NOT be escaped
        assert "#set page" in result

    def test_conditional_block(self):
        with_note = render_template(
            f"{FIXTURES}/simple.j2.typ",
            {"title": "T", "body": "B", "note": "Important"},
        )
        assert "Important" in with_note

        without_note = render_template(
            f"{FIXTURES}/simple.j2.typ",
            {"title": "T", "body": "B", "note": ""},
        )
        assert "_Note:" not in without_note
