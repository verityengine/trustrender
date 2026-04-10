"""Tests for the CLI entry point."""

from pathlib import Path

from typeset.cli import main

FIXTURES = Path("tests/fixtures")


class TestCLIRender:
    def test_renders_pdf(self, tmp_path):
        out = tmp_path / "out.pdf"
        code = main([
            "render",
            str(FIXTURES / "simple.j2.typ"),
            str(FIXTURES / "simple.json"),
            "-o", str(out),
        ])
        assert code == 0
        assert out.exists()
        assert out.read_bytes()[:5] == b"%PDF-"

    def test_renders_static_typ(self, tmp_path):
        out = tmp_path / "out.pdf"
        # Static .typ files don't need real data, pass empty JSON
        data = tmp_path / "empty.json"
        data.write_text("{}")
        code = main([
            "render",
            str(FIXTURES / "simple.typ"),
            str(data),
            "-o", str(out),
        ])
        assert code == 0
        assert out.exists()

    def test_error_exit_code(self, tmp_path):
        out = tmp_path / "out.pdf"
        code = main([
            "render",
            "nonexistent.j2.typ",
            str(FIXTURES / "simple.json"),
            "-o", str(out),
        ])
        assert code == 1

    def test_no_command_shows_help(self, capsys):
        code = main([])
        assert code == 1

    def test_debug_flag(self, tmp_path):
        out = tmp_path / "out.pdf"
        code = main([
            "render",
            str(FIXTURES / "simple.j2.typ"),
            str(FIXTURES / "simple.json"),
            "-o", str(out),
            "--debug",
        ])
        assert code == 0
        # Clean up intermediate files
        for f in FIXTURES.glob("_typeset_*.typ"):
            f.unlink()
