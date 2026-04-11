"""Tests for compilation backends, factory, and cross-backend parity.

The most important tests here are the parity tests: same inputs produce
the same ErrorCode classification and the same valid output regardless
of which backend executes.
"""

from __future__ import annotations

import shutil
from pathlib import Path
from unittest import mock

import pytest

from formforge.engine import (
    CompileBackend,
    TypstCliBackend,
    TypstPyBackend,
    compile_typst,
    compile_typst_file,
    get_backend,
)
from formforge.errors import ErrorCode, FormforgeError

FIXTURES = Path(__file__).parent / "fixtures"
HAS_TYPST_CLI = shutil.which("typst") is not None


# ---------------------------------------------------------------------------
# Protocol compliance
# ---------------------------------------------------------------------------


class TestProtocolCompliance:
    def test_typst_py_satisfies_protocol(self):
        assert isinstance(TypstPyBackend(), CompileBackend)

    def test_typst_cli_satisfies_protocol(self):
        assert isinstance(TypstCliBackend(), CompileBackend)


# ---------------------------------------------------------------------------
# Factory: get_backend()
# ---------------------------------------------------------------------------


class TestGetBackend:
    def test_force_typst_py(self):
        b = get_backend(force="typst-py")
        assert isinstance(b, TypstPyBackend)

    def test_force_typst_cli(self):
        b = get_backend(force="typst-cli")
        assert isinstance(b, TypstCliBackend)

    def test_force_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown backend"):
            get_backend(force="weasyprint")

    def test_env_var_typst_cli(self, monkeypatch):
        monkeypatch.setenv("FORMFORGE_BACKEND", "typst-cli")
        b = get_backend()
        assert isinstance(b, TypstCliBackend)

    def test_env_var_typst_py(self, monkeypatch):
        monkeypatch.setenv("FORMFORGE_BACKEND", "typst-py")
        b = get_backend()
        assert isinstance(b, TypstPyBackend)

    def test_auto_detect_prefers_typst_py(self, monkeypatch):
        monkeypatch.delenv("FORMFORGE_BACKEND", raising=False)
        b = get_backend()
        # typst-py is installed in test env, so should get TypstPyBackend
        assert isinstance(b, TypstPyBackend)

    def test_auto_detect_falls_back_to_cli(self, monkeypatch):
        monkeypatch.delenv("FORMFORGE_BACKEND", raising=False)
        # Block the typst import so auto-detect falls back
        with mock.patch.dict("sys.modules", {"typst": None}):
            b = get_backend()
            assert isinstance(b, TypstCliBackend)

    def test_force_beats_env_var(self, monkeypatch):
        """force parameter takes precedence over FORMFORGE_BACKEND env var."""
        monkeypatch.setenv("FORMFORGE_BACKEND", "typst-cli")
        b = get_backend(force="typst-py")
        assert isinstance(b, TypstPyBackend)

    def test_env_var_beats_auto_detect(self, monkeypatch):
        """Env var takes precedence over auto-detect."""
        monkeypatch.setenv("FORMFORGE_BACKEND", "typst-cli")
        b = get_backend()
        assert isinstance(b, TypstCliBackend)

    def test_fresh_instance_each_call(self):
        """No caching — each call returns a new instance."""
        a = get_backend(force="typst-py")
        b = get_backend(force="typst-py")
        assert a is not b


# ---------------------------------------------------------------------------
# TypstPyBackend
# ---------------------------------------------------------------------------


class TestTypstPyBackend:
    def test_compile_simple(self):
        backend = TypstPyBackend()
        pdf = backend.compile(FIXTURES / "simple.typ")
        assert pdf[:5] == b"%PDF-"
        assert len(pdf) > 500

    def test_compile_bad_syntax(self):
        backend = TypstPyBackend()
        with pytest.raises(FormforgeError) as exc_info:
            backend.compile(FIXTURES / "bad_syntax.typ")
        assert exc_info.value.code == ErrorCode.COMPILE_ERROR
        assert exc_info.value.stage == "compilation"

    def test_compile_missing_asset(self):
        backend = TypstPyBackend()
        with pytest.raises(FormforgeError) as exc_info:
            backend.compile(FIXTURES / "missing_image_static.typ")
        assert exc_info.value.code == ErrorCode.MISSING_ASSET

    def test_font_paths_accepted(self):
        backend = TypstPyBackend()
        fonts_dir = Path(__file__).parent.parent / "fonts"
        font_paths = [str(fonts_dir)] if fonts_dir.is_dir() else None
        pdf = backend.compile(FIXTURES / "simple.typ", font_paths=font_paths)
        assert pdf[:5] == b"%PDF-"


# ---------------------------------------------------------------------------
# TypstCliBackend
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HAS_TYPST_CLI, reason="typst CLI not on PATH")
class TestTypstCliBackend:
    def test_compile_simple(self):
        backend = TypstCliBackend()
        pdf = backend.compile(FIXTURES / "simple.typ")
        assert pdf[:5] == b"%PDF-"
        assert len(pdf) > 500

    def test_compile_bad_syntax(self):
        backend = TypstCliBackend()
        with pytest.raises(FormforgeError) as exc_info:
            backend.compile(FIXTURES / "bad_syntax.typ")
        assert exc_info.value.code == ErrorCode.COMPILE_ERROR
        assert exc_info.value.stage == "compilation"
        assert exc_info.value.detail  # stderr captured

    def test_compile_missing_asset(self):
        backend = TypstCliBackend()
        with pytest.raises(FormforgeError) as exc_info:
            backend.compile(FIXTURES / "missing_image_static.typ")
        assert exc_info.value.code == ErrorCode.MISSING_ASSET

    def test_font_paths_passed(self):
        backend = TypstCliBackend()
        fonts_dir = Path(__file__).parent.parent / "fonts"
        font_paths = [str(fonts_dir)] if fonts_dir.is_dir() else None
        pdf = backend.compile(FIXTURES / "simple.typ", font_paths=font_paths)
        assert pdf[:5] == b"%PDF-"

    def test_timeout_raises_render_timeout(self):
        backend = TypstCliBackend(compile_timeout=0.001)
        with pytest.raises(FormforgeError) as exc_info:
            backend.compile(FIXTURES / "simple.typ")
        assert exc_info.value.code == ErrorCode.RENDER_TIMEOUT

    def test_missing_binary_raises_backend_error(self):
        backend = TypstCliBackend(typst_bin="/nonexistent/typst")
        with pytest.raises(FormforgeError) as exc_info:
            backend.compile(FIXTURES / "simple.typ")
        exc = exc_info.value
        assert exc.code == ErrorCode.BACKEND_ERROR
        assert "not found" in str(exc).lower()
        assert "FORMFORGE_BACKEND=typst-py" in str(exc)

    def test_missing_binary_message_includes_install_guidance(self):
        backend = TypstCliBackend(typst_bin="/nonexistent/typst")
        with pytest.raises(FormforgeError, match="Install Typst"):
            backend.compile(FIXTURES / "simple.typ")


# ---------------------------------------------------------------------------
# Cross-backend parity (the most important tests)
# ---------------------------------------------------------------------------


BOTH_BACKENDS = [
    pytest.param("typst-py", id="typst-py"),
    pytest.param(
        "typst-cli",
        id="typst-cli",
        marks=pytest.mark.skipif(not HAS_TYPST_CLI, reason="typst CLI not on PATH"),
    ),
]


def _make_backend(name: str) -> CompileBackend:
    return get_backend(force=name)


class TestCrossBackendParity:
    """Same inputs, same outputs, same error codes — regardless of backend."""

    @pytest.mark.parametrize("backend_name", BOTH_BACKENDS)
    def test_simple_fixture_produces_valid_pdf(self, backend_name):
        backend = _make_backend(backend_name)
        pdf = backend.compile(FIXTURES / "simple.typ")
        assert pdf[:5] == b"%PDF-"
        assert len(pdf) > 500

    @pytest.mark.parametrize("backend_name", BOTH_BACKENDS)
    def test_bad_syntax_classifies_as_compile_error(self, backend_name):
        """Real Typst syntax error (not synthetic) produces COMPILE_ERROR."""
        backend = _make_backend(backend_name)
        with pytest.raises(FormforgeError) as exc_info:
            backend.compile(FIXTURES / "bad_syntax.typ")
        assert exc_info.value.code == ErrorCode.COMPILE_ERROR
        assert exc_info.value.stage == "compilation"

    @pytest.mark.parametrize("backend_name", BOTH_BACKENDS)
    def test_missing_asset_classifies_as_missing_asset(self, backend_name):
        """Real missing-image error produces MISSING_ASSET under both."""
        backend = _make_backend(backend_name)
        with pytest.raises(FormforgeError) as exc_info:
            backend.compile(FIXTURES / "missing_image_static.typ")
        assert exc_info.value.code == ErrorCode.MISSING_ASSET

    @pytest.mark.parametrize("backend_name", BOTH_BACKENDS)
    def test_font_paths_work(self, backend_name):
        """Bundled font directory works under both backends."""
        backend = _make_backend(backend_name)
        fonts_dir = Path(__file__).parent.parent / "fonts"
        font_paths = [str(fonts_dir)] if fonts_dir.is_dir() else None
        pdf = backend.compile(FIXTURES / "simple.typ", font_paths=font_paths)
        assert pdf[:5] == b"%PDF-"

    @pytest.mark.parametrize("backend_name", BOTH_BACKENDS)
    def test_error_has_source_path(self, backend_name):
        """Both backends set source_path on compile errors."""
        backend = _make_backend(backend_name)
        with pytest.raises(FormforgeError) as exc_info:
            backend.compile(FIXTURES / "bad_syntax.typ")
        assert exc_info.value.source_path is not None
        assert "bad_syntax.typ" in exc_info.value.source_path


# ---------------------------------------------------------------------------
# compile_typst_file()
# ---------------------------------------------------------------------------


class TestCompileTypstFile:
    def test_compiles_static_typ(self):
        pdf = compile_typst_file(FIXTURES / "simple.typ")
        assert pdf[:5] == b"%PDF-"

    def test_error_carries_template_path(self):
        with pytest.raises(FormforgeError) as exc_info:
            compile_typst_file(FIXTURES / "bad_syntax.typ")
        assert exc_info.value.template_path is not None
        assert "bad_syntax.typ" in exc_info.value.template_path

    def test_missing_asset_error(self):
        with pytest.raises(FormforgeError) as exc_info:
            compile_typst_file(FIXTURES / "missing_image_static.typ")
        assert exc_info.value.code == ErrorCode.MISSING_ASSET


# ---------------------------------------------------------------------------
# Timeout and backend parameter threading
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not HAS_TYPST_CLI, reason="typst CLI not on PATH")
class TestTimeoutThreading:
    """Verify timeout parameter flows through compile functions to backend."""

    def test_compile_typst_file_with_explicit_backend(self):
        """compile_typst_file(backend=...) uses the provided backend."""
        backend = TypstCliBackend()
        pdf = compile_typst_file(FIXTURES / "simple.typ", backend=backend)
        assert pdf[:5] == b"%PDF-"

    def test_compile_typst_file_timeout_kills(self):
        """CLI backend subprocess is killed on timeout."""
        backend = TypstCliBackend()
        with pytest.raises(FormforgeError) as exc_info:
            compile_typst_file(
                FIXTURES / "simple.typ",
                backend=backend,
                timeout=0.001,
            )
        assert exc_info.value.code == ErrorCode.RENDER_TIMEOUT

    def test_compile_typst_with_explicit_backend(self, tmp_path):
        """compile_typst(backend=...) uses the provided backend."""
        source = '#set page(paper: "us-letter")\n= Hello\n'
        backend = TypstCliBackend()
        pdf = compile_typst(source, tmp_path, backend=backend)
        assert pdf[:5] == b"%PDF-"

    def test_compile_typst_timeout_kills(self, tmp_path):
        """CLI backend subprocess is killed on timeout through compile_typst."""
        source = '#set page(paper: "us-letter")\n= Hello\n'
        backend = TypstCliBackend()
        with pytest.raises(FormforgeError) as exc_info:
            compile_typst(source, tmp_path, backend=backend, timeout=0.001)
        assert exc_info.value.code == ErrorCode.RENDER_TIMEOUT

    def test_timeout_cleanup_policy_no_debug(self, tmp_path):
        """On timeout without debug, temp file is cleaned up (no accumulation)."""
        source = '#set page(paper: "us-letter")\n= Hello\n'
        backend = TypstCliBackend()
        before = set(tmp_path.glob("_formforge_*"))
        with pytest.raises(FormforgeError) as exc_info:
            compile_typst(source, tmp_path, backend=backend, timeout=0.001, debug=False)
        assert exc_info.value.code == ErrorCode.RENDER_TIMEOUT
        after = set(tmp_path.glob("_formforge_*"))
        assert after == before, "Temp file should be cleaned up on timeout (non-debug)"

    def test_timeout_cleanup_policy_debug(self, tmp_path):
        """On timeout with debug=True, temp file is preserved."""
        source = '#set page(paper: "us-letter")\n= Hello\n'
        backend = TypstCliBackend()
        before = set(tmp_path.glob("_formforge_*"))
        with pytest.raises(FormforgeError) as exc_info:
            compile_typst(source, tmp_path, backend=backend, timeout=0.001, debug=True)
        assert exc_info.value.code == ErrorCode.RENDER_TIMEOUT
        after = set(tmp_path.glob("_formforge_*"))
        new_files = after - before
        assert len(new_files) == 1, "Temp file should be preserved on timeout with debug"
        # Cleanup
        for f in new_files:
            f.unlink()

    def test_per_call_timeout_overrides_default(self):
        """timeout= on compile() overrides TypstCliBackend's compile_timeout."""
        # Backend has generous default (60s), but per-call is tiny
        backend = TypstCliBackend(compile_timeout=60)
        with pytest.raises(FormforgeError) as exc_info:
            backend.compile(FIXTURES / "simple.typ", timeout=0.001)
        assert exc_info.value.code == ErrorCode.RENDER_TIMEOUT
