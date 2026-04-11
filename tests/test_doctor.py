"""Tests for trustrender doctor command."""

from __future__ import annotations

from unittest.mock import patch

from trustrender.doctor import (
    FAIL,
    OK,
    WARN,
    check_backends,
    check_env_backend,
    check_env_font_path,
    check_fonts_dir,
    check_trustrender_import,
    check_python_version,
    check_smoke_render,
    check_smoke_server,
    check_typst_cli,
    check_typst_py,
    run_doctor,
)


class TestIndividualChecks:
    def test_python_version_passes(self):
        status, msg = check_python_version()
        assert status == OK
        assert "3.1" in msg  # 3.11 or 3.12

    def test_trustrender_import(self):
        status, msg = check_trustrender_import()
        assert status == OK
        assert "0.1.0" in msg

    def test_typst_py(self):
        status, msg = check_typst_py()
        assert status == OK
        assert "typst-py" in msg

    def test_typst_cli(self):
        status, msg = check_typst_cli()
        # May or may not be installed, but should not crash
        assert status in (OK, WARN)

    def test_fonts_dir(self):
        status, msg = check_fonts_dir()
        assert status == OK
        assert "4 files" in msg

    def test_env_backend_not_set(self):
        with patch.dict("os.environ", {}, clear=False):
            # Remove TRUSTRENDER_BACKEND if present
            env = dict(**__import__("os").environ)
            env.pop("TRUSTRENDER_BACKEND", None)
            with patch.dict("os.environ", env, clear=True):
                status, msg = check_env_backend()
                assert status == "info"
                assert "auto-detect" in msg

    def test_env_font_path_not_set(self):
        env = dict(**__import__("os").environ)
        env.pop("TRUSTRENDER_FONT_PATH", None)
        with patch.dict("os.environ", env, clear=True):
            status, msg = check_env_font_path()
            assert status == "info"
            assert "bundled" in msg


class TestBackendLogic:
    def test_both_available(self):
        status, msg = check_backends(OK, OK)
        assert status == OK
        assert "Both" in msg

    def test_py_only(self):
        status, msg = check_backends(OK, WARN)
        assert status == WARN
        assert "server mode" in msg

    def test_cli_only(self):
        status, msg = check_backends(WARN, OK)
        assert status == OK

    def test_neither_available(self):
        status, msg = check_backends(WARN, WARN)
        assert status == FAIL
        assert "No backend" in msg


class TestSmokeChecks:
    def test_smoke_render(self):
        status, msg = check_smoke_render()
        assert status == OK
        assert "KB" in msg

    def test_smoke_server(self):
        status, msg = check_smoke_server()
        assert status == OK
        assert "/health" in msg


class TestRunDoctor:
    def test_returns_zero(self):
        assert run_doctor() == 0

    def test_returns_zero_with_smoke(self):
        assert run_doctor(smoke=True) == 0


class TestCliIntegration:
    def test_doctor_command(self):
        from trustrender.cli import main

        assert main(["doctor"]) == 0

    def test_doctor_smoke_command(self):
        from trustrender.cli import main

        assert main(["doctor", "--smoke"]) == 0


class TestDoctorFontEnhancements:
    """Tests for enhanced font inventory: stack parsing, actionable fixes, env path."""

    def test_font_stack_detected(self, tmp_path):
        """Font stacks like font: ("Inter", "Noto") should detect both names."""
        from trustrender.doctor import check_template_fonts

        template = tmp_path / "test.j2.typ"
        template.write_text('#set text(font: ("Inter", "Noto Sans"))\nHello')

        with patch("trustrender.bundled_font_dir", return_value=None), \
             patch("trustrender.doctor._find_repo_root", return_value=None):
            status, msg = check_template_fonts(templates_dir=tmp_path)
        assert "Inter" in msg
        assert "Noto Sans" in msg

    def test_single_font_still_works(self, tmp_path):
        """Single font declarations still detected after refactor."""
        from trustrender.doctor import check_template_fonts

        template = tmp_path / "test.j2.typ"
        template.write_text('#set text(font: "Roboto")\nHello')

        with patch("trustrender.bundled_font_dir", return_value=None), \
             patch("trustrender.doctor._find_repo_root", return_value=None):
            status, msg = check_template_fonts(templates_dir=tmp_path)
        assert "Roboto" in msg
        assert status == WARN  # not available

    def test_mixed_single_and_stack(self, tmp_path):
        """Templates with both single fonts and stacks should list all."""
        from trustrender.doctor import check_template_fonts

        template = tmp_path / "test.j2.typ"
        template.write_text(
            '#set text(font: "Inter")\n'
            '#show heading: set text(font: ("Roboto", "Arial"))\n'
        )

        with patch("trustrender.bundled_font_dir", return_value=None), \
             patch("trustrender.doctor._find_repo_root", return_value=None):
            status, msg = check_template_fonts(templates_dir=tmp_path)
        assert "Inter" in msg
        assert "Roboto" in msg
        assert "Arial" in msg

    def test_missing_inter_shows_download_fix(self, tmp_path):
        """When Inter is missing, doctor should suggest downloading it."""
        from trustrender.doctor import check_template_fonts

        template = tmp_path / "test.j2.typ"
        template.write_text('#set text(font: "Inter")\nHello')

        with patch("trustrender.bundled_font_dir", return_value=None), \
             patch("trustrender.doctor._find_repo_root", return_value=None):
            env = dict(**__import__("os").environ)
            env.pop("TRUSTRENDER_FONT_PATH", None)
            with patch.dict("os.environ", env, clear=True):
                status, msg = check_template_fonts(templates_dir=tmp_path)
        assert "download Inter" in msg
        assert "fonts.google.com" in msg

    def test_missing_font_shows_target_path(self, tmp_path):
        """When TRUSTRENDER_FONT_PATH is set, doctor should suggest installing there."""
        from trustrender.doctor import check_template_fonts

        font_dir = tmp_path / "fonts"
        font_dir.mkdir()

        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        template = template_dir / "test.j2.typ"
        template.write_text('#set text(font: "CustomFont")\nHello')

        with patch("trustrender.bundled_font_dir", return_value=None), \
             patch("trustrender.doctor._find_repo_root", return_value=None), \
             patch.dict("os.environ", {"TRUSTRENDER_FONT_PATH": str(font_dir)}):
            status, msg = check_template_fonts(templates_dir=template_dir)
        assert status == WARN
        assert str(font_dir) in msg

    def test_font_path_env_inventory(self, tmp_path):
        """When TRUSTRENDER_FONT_PATH has fonts, doctor should show inventory."""
        from trustrender.doctor import check_template_fonts

        font_dir = tmp_path / "fonts"
        font_dir.mkdir()
        (font_dir / "Roboto-Regular.ttf").write_bytes(b"fake")

        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        template = template_dir / "test.j2.typ"
        template.write_text('#set text(font: "Inter")\nHello')

        with patch("trustrender.bundled_font_dir", return_value=None), \
             patch("trustrender.doctor._find_repo_root", return_value=None), \
             patch.dict("os.environ", {"TRUSTRENDER_FONT_PATH": str(font_dir)}):
            status, msg = check_template_fonts(templates_dir=template_dir)
        assert "Env path:" in msg
        assert "roboto" in msg.lower()

    def test_font_path_env_empty_dir_no_crash(self, tmp_path):
        """Empty TRUSTRENDER_FONT_PATH directory should not crash."""
        from trustrender.doctor import check_template_fonts

        font_dir = tmp_path / "fonts"
        font_dir.mkdir()

        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        template = template_dir / "test.j2.typ"
        template.write_text('#set text(font: "Inter")\nHello')

        with patch("trustrender.bundled_font_dir", return_value=None), \
             patch("trustrender.doctor._find_repo_root", return_value=None), \
             patch.dict("os.environ", {"TRUSTRENDER_FONT_PATH": str(font_dir)}):
            status, msg = check_template_fonts(templates_dir=template_dir)
        assert status == WARN
        assert "Inter" in msg


class TestFailurePaths:
    """Test the most important failure: no backend available."""

    def test_no_backends_fails(self):
        """Doctor with neither backend should fail with clear message."""
        status, msg = check_backends(WARN, WARN)
        assert status == FAIL
        assert "No backend available" in msg
        assert "pip install" in msg
        assert "brew install typst" in msg

    def test_typst_py_import_fails(self):
        """When typst-py import fails, check returns WARN not FAIL."""
        import importlib.metadata as im

        with patch(
            "trustrender.doctor.importlib.metadata.version",
            side_effect=im.PackageNotFoundError,
        ):
            status, msg = check_typst_py()
            assert status == WARN
            assert "typst-cli backend" in msg

    def test_typst_cli_not_found(self):
        """When typst CLI is not on PATH, check returns WARN with install instructions."""
        with patch("trustrender.doctor.subprocess.run", side_effect=FileNotFoundError):
            status, msg = check_typst_cli()
            assert status == WARN
            assert "brew install typst" in msg
            assert "server mode" in msg
