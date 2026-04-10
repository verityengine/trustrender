"""Tests for the core render() API."""

import json
from pathlib import Path

import pytest

from typeset import TypesetError, render

FIXTURES = Path("tests/fixtures")


class TestRenderJinjaTemplate:
    def test_returns_pdf_bytes(self):
        pdf = render(FIXTURES / "simple.j2.typ", FIXTURES / "simple.json")
        assert pdf[:5] == b"%PDF-"

    def test_writes_output_file(self, tmp_path):
        out = tmp_path / "out.pdf"
        pdf = render(FIXTURES / "simple.j2.typ", FIXTURES / "simple.json", output=out)
        assert out.exists()
        assert out.read_bytes() == pdf

    def test_creates_output_directories(self, tmp_path):
        out = tmp_path / "sub" / "dir" / "out.pdf"
        render(FIXTURES / "simple.j2.typ", FIXTURES / "simple.json", output=out)
        assert out.exists()

    def test_with_image(self):
        pdf = render(
            FIXTURES / "with_image.j2.typ",
            {"title": "Logo Test"},
        )
        assert pdf[:5] == b"%PDF-"

    def test_escapes_special_chars_in_data(self):
        pdf = render(
            FIXTURES / "simple.j2.typ",
            {"title": "Cost: $500 #items @ref", "body": "Ok", "note": ""},
        )
        assert pdf[:5] == b"%PDF-"


class TestRenderStaticTemplate:
    def test_renders_raw_typ(self):
        pdf = render(FIXTURES / "simple.typ", {})
        assert pdf[:5] == b"%PDF-"


class TestDataResolution:
    def test_dict_data(self):
        pdf = render(
            FIXTURES / "simple.j2.typ",
            {"title": "Dict", "body": "From dict", "note": ""},
        )
        assert pdf[:5] == b"%PDF-"

    def test_json_file_path(self):
        pdf = render(FIXTURES / "simple.j2.typ", FIXTURES / "simple.json")
        assert pdf[:5] == b"%PDF-"

    def test_json_file_path_as_string(self):
        pdf = render(FIXTURES / "simple.j2.typ", str(FIXTURES / "simple.json"))
        assert pdf[:5] == b"%PDF-"

    def test_json_string_data(self):
        data = json.dumps({"title": "JSON", "body": "From string", "note": ""})
        pdf = render(FIXTURES / "simple.j2.typ", data)
        assert pdf[:5] == b"%PDF-"

    def test_invalid_json_string(self):
        with pytest.raises(TypesetError, match="Invalid data"):
            render(FIXTURES / "simple.j2.typ", "not json at all {{{")

    def test_json_array_rejected(self):
        with pytest.raises(TypesetError, match="must be an object"):
            render(FIXTURES / "simple.j2.typ", "[1, 2, 3]")


class TestDebugMode:
    @pytest.fixture(autouse=True)
    def _clean_intermediates(self):
        """Remove any leftover intermediate files before and after each test."""
        for f in FIXTURES.glob("_typeset_*.typ"):
            f.unlink()
        yield
        for f in FIXTURES.glob("_typeset_*.typ"):
            f.unlink()

    def test_debug_preserves_intermediate(self):
        render(
            FIXTURES / "simple.j2.typ",
            FIXTURES / "simple.json",
            debug=True,
        )
        intermediates = list(FIXTURES.glob("_typeset_*.typ"))
        assert len(intermediates) == 1

    def test_no_debug_cleans_up(self):
        render(FIXTURES / "simple.j2.typ", FIXTURES / "simple.json")
        intermediates = list(FIXTURES.glob("_typeset_*.typ"))
        assert len(intermediates) == 0


class TestFileNotFound:
    def test_missing_template(self):
        with pytest.raises(FileNotFoundError, match="Template not found"):
            render("nonexistent.j2.typ", {})
