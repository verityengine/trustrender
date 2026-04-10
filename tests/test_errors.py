"""Tests for error surfaces — can a developer debug these failures?"""

from pathlib import Path

import pytest

from typeset import TypesetError, render

FIXTURES = Path("tests/fixtures")


class TestMissingImage:
    def test_raises_typeset_error(self):
        with pytest.raises(TypesetError, match="file not found"):
            render(FIXTURES / "missing_image.j2.typ", {"title": "Test"})

    def test_preserves_intermediate_file(self):
        try:
            render(FIXTURES / "missing_image.j2.typ", {"title": "Test"})
        except TypesetError as exc:
            assert exc.source_path is not None
            assert Path(exc.source_path).exists()
            # Clean up
            Path(exc.source_path).unlink()
        else:
            pytest.fail("Expected TypesetError")


class TestBadSyntax:
    def test_raises_typeset_error(self):
        with pytest.raises(TypesetError, match="expected length"):
            render(FIXTURES / "bad_syntax.typ", {})


class TestMissingVariable:
    def test_missing_jinja_variable_renders_empty(self):
        # Jinja2 renders undefined variables as empty string by default
        # This is Jinja2's behavior, not an error
        pdf = render(FIXTURES / "simple.j2.typ", {"title": "T", "body": "B"})
        assert pdf[:5] == b"%PDF-"


class TestUglyData:
    """Test with realistic messy data that could break rendering."""

    def test_currency_values(self):
        pdf = render(
            FIXTURES / "simple.j2.typ",
            {"title": "$1,000.00", "body": "Total: $99.99", "note": ""},
        )
        assert pdf[:5] == b"%PDF-"

    def test_long_text(self):
        pdf = render(
            FIXTURES / "simple.j2.typ",
            {
                "title": "Invoice",
                "body": "A" * 5000,
                "note": "B" * 1000,
            },
        )
        assert pdf[:5] == b"%PDF-"

    def test_unicode_data(self):
        pdf = render(
            FIXTURES / "simple.j2.typ",
            {
                "title": "Facture",
                "body": "Montant total TTC",
                "note": "",
            },
        )
        assert pdf[:5] == b"%PDF-"

    def test_special_chars_everywhere(self):
        pdf = render(
            FIXTURES / "simple.j2.typ",
            {
                "title": "Cost: $500 @ #1 store",
                "body": "Email: user@example.com, price: $99",
                "note": "#hashtag @mention $money",
            },
        )
        assert pdf[:5] == b"%PDF-"


class TestErrorMessageQuality:
    def test_includes_source_path_hint(self):
        try:
            render(FIXTURES / "missing_image.j2.typ", {"title": "T"})
        except TypesetError as exc:
            msg = str(exc)
            assert "Rendered source preserved at:" in msg
            # Clean up
            if exc.source_path:
                Path(exc.source_path).unlink()
        else:
            pytest.fail("Expected TypesetError")
