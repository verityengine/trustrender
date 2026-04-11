"""Tests for the CLI entry point."""

import os
from pathlib import Path
from unittest.mock import patch

from formforge.cli import main

FIXTURES = Path("tests/fixtures")


class TestCLIRender:
    def test_renders_pdf(self, tmp_path):
        out = tmp_path / "out.pdf"
        code = main(
            [
                "render",
                str(FIXTURES / "simple.j2.typ"),
                str(FIXTURES / "simple.json"),
                "-o",
                str(out),
            ]
        )
        assert code == 0
        assert out.exists()
        assert out.read_bytes()[:5] == b"%PDF-"

    def test_renders_static_typ(self, tmp_path):
        out = tmp_path / "out.pdf"
        # Static .typ files don't need real data, pass empty JSON
        data = tmp_path / "empty.json"
        data.write_text("{}")
        code = main(
            [
                "render",
                str(FIXTURES / "simple.typ"),
                str(data),
                "-o",
                str(out),
            ]
        )
        assert code == 0
        assert out.exists()

    def test_error_exit_code(self, tmp_path):
        out = tmp_path / "out.pdf"
        code = main(
            [
                "render",
                "nonexistent.j2.typ",
                str(FIXTURES / "simple.json"),
                "-o",
                str(out),
            ]
        )
        assert code == 1

    def test_no_command_shows_help(self, capsys):
        code = main([])
        assert code == 1

    def test_debug_flag(self, tmp_path):
        out = tmp_path / "out.pdf"
        code = main(
            [
                "render",
                str(FIXTURES / "simple.j2.typ"),
                str(FIXTURES / "simple.json"),
                "-o",
                str(out),
                "--debug",
            ]
        )
        assert code == 0
        # Clean up intermediate files
        for f in FIXTURES.glob("_formforge_*.typ"):
            f.unlink()


class TestCLIServeTemplatesEnv:
    """Test FORMFORGE_TEMPLATES_DIR env var support."""

    def test_missing_templates_errors(self, capsys):
        """Serve without --templates or env var prints clear error."""
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("FORMFORGE_TEMPLATES_DIR", None)
            code = main(["serve"])
        assert code == 1
        captured = capsys.readouterr()
        assert "FORMFORGE_TEMPLATES_DIR" in captured.err

    def test_env_var_is_used(self):
        """FORMFORGE_TEMPLATES_DIR is accepted when --templates is absent."""
        with patch.dict(os.environ, {"FORMFORGE_TEMPLATES_DIR": str(FIXTURES)}):
            with patch("uvicorn.run"):
                code = main(["serve"])
        assert code == 0

    def test_cli_arg_overrides_env(self):
        """--templates CLI arg takes precedence over env var."""
        with patch.dict(os.environ, {"FORMFORGE_TEMPLATES_DIR": "/wrong/path"}):
            with patch("uvicorn.run"):
                code = main(["serve", "--templates", str(FIXTURES)])
        assert code == 0
