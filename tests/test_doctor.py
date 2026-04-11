"""Tests for formforge doctor command."""

from __future__ import annotations

from unittest.mock import patch

from formforge.doctor import (
    FAIL,
    OK,
    WARN,
    check_backends,
    check_env_backend,
    check_env_font_path,
    check_fonts_dir,
    check_formforge_import,
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

    def test_formforge_import(self):
        status, msg = check_formforge_import()
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
            # Remove FORMFORGE_BACKEND if present
            env = dict(**__import__("os").environ)
            env.pop("FORMFORGE_BACKEND", None)
            with patch.dict("os.environ", env, clear=True):
                status, msg = check_env_backend()
                assert status == "info"
                assert "auto-detect" in msg

    def test_env_font_path_not_set(self):
        env = dict(**__import__("os").environ)
        env.pop("FORMFORGE_FONT_PATH", None)
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
        from formforge.cli import main

        assert main(["doctor"]) == 0

    def test_doctor_smoke_command(self):
        from formforge.cli import main

        assert main(["doctor", "--smoke"]) == 0


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
            "formforge.doctor.importlib.metadata.version",
            side_effect=im.PackageNotFoundError,
        ):
            status, msg = check_typst_py()
            assert status == WARN
            assert "typst-cli backend" in msg

    def test_typst_cli_not_found(self):
        """When typst CLI is not on PATH, check returns WARN with install instructions."""
        with patch("formforge.doctor.subprocess.run", side_effect=FileNotFoundError):
            status, msg = check_typst_cli()
            assert status == WARN
            assert "brew install typst" in msg
            assert "server mode" in msg
