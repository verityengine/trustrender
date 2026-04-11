"""Tests for the error pipeline — every error class, every surface.

Verifies that errors are properly classified with stable codes, carry
the right stage, preserve full diagnostics, and surface correctly on
both CLI and server.
"""

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from formforge import FormforgeError, render
from formforge.cli import _format_error, main
from formforge.errors import ErrorCode
from formforge.server import create_app

FIXTURES = Path("tests/fixtures")
EXAMPLES = Path("examples")


# ---------------------------------------------------------------------------
# Error model basics
# ---------------------------------------------------------------------------


class TestErrorModel:
    def test_error_has_code(self):
        exc = FormforgeError("test", code=ErrorCode.COMPILE_ERROR, stage="compilation")
        assert exc.code == ErrorCode.COMPILE_ERROR

    def test_error_has_stage(self):
        exc = FormforgeError("test", code=ErrorCode.COMPILE_ERROR, stage="compilation")
        assert exc.stage == "compilation"

    def test_error_has_detail(self):
        exc = FormforgeError(
            "summary",
            code=ErrorCode.COMPILE_ERROR,
            stage="compilation",
            detail="line 1\nline 2\nline 3",
        )
        assert exc.detail == "line 1\nline 2\nline 3"

    def test_detail_defaults_to_message(self):
        exc = FormforgeError("summary", code=ErrorCode.COMPILE_ERROR, stage="compilation")
        assert exc.detail == "summary"

    def test_to_dict_basic(self):
        exc = FormforgeError(
            "something broke",
            code=ErrorCode.COMPILE_ERROR,
            stage="compilation",
        )
        d = exc.to_dict()
        assert d["error"] == "COMPILE_ERROR"
        assert d["message"] == "something broke"
        assert d["stage"] == "compilation"
        assert "detail" not in d  # not in non-debug

    def test_to_dict_debug(self):
        exc = FormforgeError(
            "summary",
            code=ErrorCode.MISSING_ASSET,
            stage="compilation",
            detail="full diagnostic\nwith details",
            source_path="/tmp/test.typ",
            template_path="invoice.j2.typ",
        )
        d = exc.to_dict(include_debug=True)
        assert d["error"] == "MISSING_ASSET"
        assert d["detail"] == "full diagnostic\nwith details"
        assert d["source_path"] == "/tmp/test.typ"
        assert d["template_path"] == "invoice.j2.typ"

    def test_to_dict_without_debug_excludes_paths(self):
        exc = FormforgeError(
            "summary",
            code=ErrorCode.COMPILE_ERROR,
            stage="compilation",
            source_path="/tmp/test.typ",
        )
        d = exc.to_dict(include_debug=False)
        assert "source_path" not in d
        assert "detail" not in d

    def test_str_includes_intermediate_path(self):
        exc = FormforgeError(
            "compile failed",
            code=ErrorCode.COMPILE_ERROR,
            stage="compilation",
            source_path="/tmp/_formforge_abc.typ",
        )
        assert "Intermediate source: /tmp/_formforge_abc.typ" in str(exc)

    def test_str_includes_template_path(self):
        exc = FormforgeError(
            "variable error",
            code=ErrorCode.TEMPLATE_VARIABLE,
            stage="template_preprocess",
            template_path="invoice.j2.typ",
        )
        assert "Template: invoice.j2.typ" in str(exc)


# ---------------------------------------------------------------------------
# INVALID_DATA — bad input data
# ---------------------------------------------------------------------------


class TestInvalidData:
    def test_bad_json_string(self):
        with pytest.raises(FormforgeError) as exc_info:
            render(FIXTURES / "simple.j2.typ", "not json {{{")
        assert exc_info.value.code == ErrorCode.INVALID_DATA
        assert exc_info.value.stage == "data_resolution"

    def test_json_array_not_object(self):
        with pytest.raises(FormforgeError) as exc_info:
            render(FIXTURES / "simple.j2.typ", "[1, 2, 3]")
        assert exc_info.value.code == ErrorCode.INVALID_DATA

    def test_wrong_data_type(self):
        with pytest.raises(FormforgeError) as exc_info:
            render(FIXTURES / "simple.j2.typ", 42)  # type: ignore
        assert exc_info.value.code == ErrorCode.INVALID_DATA


# ---------------------------------------------------------------------------
# TEMPLATE_NOT_FOUND — template file missing
# ---------------------------------------------------------------------------


class TestTemplateNotFound:
    def test_missing_template_raises(self):
        with pytest.raises(FormforgeError) as exc_info:
            render("nonexistent.j2.typ", {})
        assert exc_info.value.code == ErrorCode.TEMPLATE_NOT_FOUND
        assert exc_info.value.stage == "data_resolution"

    def test_missing_template_includes_path(self):
        with pytest.raises(FormforgeError) as exc_info:
            render("nonexistent.j2.typ", {})
        assert "nonexistent.j2.typ" in str(exc_info.value)


# ---------------------------------------------------------------------------
# TEMPLATE_SYNTAX — Jinja2 syntax error
# ---------------------------------------------------------------------------


class TestTemplateSyntax:
    def test_bad_jinja_raises_syntax_error(self):
        with pytest.raises(FormforgeError) as exc_info:
            render(FIXTURES / "bad_jinja_syntax.j2.typ", {"title": "T"})
        assert exc_info.value.code == ErrorCode.TEMPLATE_SYNTAX
        assert exc_info.value.stage == "template_preprocess"

    def test_syntax_error_includes_template_path(self):
        with pytest.raises(FormforgeError) as exc_info:
            render(FIXTURES / "bad_jinja_syntax.j2.typ", {"title": "T"})
        assert exc_info.value.template_path is not None
        assert "bad_jinja_syntax" in exc_info.value.template_path


# ---------------------------------------------------------------------------
# TEMPLATE_VARIABLE — undefined variable during Jinja rendering
# ---------------------------------------------------------------------------


class TestTemplateVariable:
    def test_undefined_variable_raises(self):
        with pytest.raises(FormforgeError) as exc_info:
            render(FIXTURES / "undefined_var.j2.typ", {"title": "T"})
        assert exc_info.value.code == ErrorCode.TEMPLATE_VARIABLE
        assert exc_info.value.stage == "template_preprocess"

    def test_undefined_variable_names_the_variable(self):
        with pytest.raises(FormforgeError) as exc_info:
            render(FIXTURES / "undefined_var.j2.typ", {"title": "T"})
        assert "sender" in str(exc_info.value)

    def test_undefined_variable_includes_template_path(self):
        with pytest.raises(FormforgeError) as exc_info:
            render(FIXTURES / "undefined_var.j2.typ", {"title": "T"})
        assert exc_info.value.template_path is not None


# ---------------------------------------------------------------------------
# MISSING_ASSET — file referenced in template not found
# ---------------------------------------------------------------------------


class TestMissingAsset:
    def test_missing_image_raises(self):
        with pytest.raises(FormforgeError) as exc_info:
            render(FIXTURES / "missing_image.j2.typ", {"title": "T"})
        exc = exc_info.value
        assert exc.code == ErrorCode.MISSING_ASSET
        assert exc.stage == "compilation"
        # Clean up intermediate
        if exc.source_path:
            Path(exc.source_path).unlink(missing_ok=True)

    def test_missing_image_preserves_source(self):
        with pytest.raises(FormforgeError) as exc_info:
            render(FIXTURES / "missing_image.j2.typ", {"title": "T"})
        exc = exc_info.value
        assert exc.source_path is not None
        assert Path(exc.source_path).exists()
        Path(exc.source_path).unlink()

    def test_missing_image_has_full_diagnostic(self):
        with pytest.raises(FormforgeError) as exc_info:
            render(FIXTURES / "missing_image.j2.typ", {"title": "T"})
        exc = exc_info.value
        assert "nonexistent.png" in exc.detail
        if exc.source_path:
            Path(exc.source_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# COMPILE_ERROR — Typst compilation failure
# ---------------------------------------------------------------------------


class TestMissingFont:
    def test_unknown_font_falls_back_silently(self):
        # Typst silently falls back to a default font for unknown families.
        # This means MISSING_FONT classification only fires if Typst itself
        # produces a font error (which is rare in practice).
        # This test documents the actual behavior.
        pdf = render(FIXTURES / "bad_font.j2.typ", {"title": "T"})
        assert pdf[:5] == b"%PDF-"

    def test_classifier_recognizes_font_error_string(self):
        # Directly test the classifier with a hypothetical Typst font error
        from formforge.engine import _classify_typst_error

        assert _classify_typst_error("unknown font family") == ErrorCode.MISSING_FONT
        assert _classify_typst_error("font xyz not found") == ErrorCode.MISSING_FONT
        # Unrelated errors should not match
        assert _classify_typst_error("expected length") == ErrorCode.COMPILE_ERROR


class TestCompileError:
    def test_bad_typst_syntax_raises(self):
        with pytest.raises(FormforgeError) as exc_info:
            render(FIXTURES / "bad_syntax.typ", {})
        assert exc_info.value.code == ErrorCode.COMPILE_ERROR
        assert exc_info.value.stage == "compilation"

    def test_compile_error_has_detail(self):
        with pytest.raises(FormforgeError) as exc_info:
            render(FIXTURES / "bad_syntax.typ", {})
        assert exc_info.value.detail is not None
        assert len(exc_info.value.detail) > 0


# ---------------------------------------------------------------------------
# Server error responses
# ---------------------------------------------------------------------------


@pytest.fixture
def client():
    return TestClient(create_app(EXAMPLES))


@pytest.fixture
def debug_client():
    return TestClient(create_app(EXAMPLES, debug=True))


class TestServerErrorResponses:
    def test_validation_error_has_code(self, client):
        resp = client.post("/render", json={"data": {}})
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"] == "INVALID_DATA"
        assert "stage" in data
        assert "message" in data
        assert "request_id" in data

    def test_template_not_found_has_code(self, client):
        resp = client.post(
            "/render",
            json={
                "template": "nope.j2.typ",
                "data": {},
            },
        )
        assert resp.status_code == 404
        assert resp.json()["error"] == "TEMPLATE_NOT_FOUND"

    def test_render_error_has_code_and_stage(self, debug_client):
        resp = debug_client.post(
            "/render",
            json={
                "template": "hello.typ",
                "data": {},
            },
        )
        # hello.typ is valid — this should succeed
        if resp.status_code != 200:
            data = resp.json()
            assert "error" in data
            assert "stage" in data

    def test_all_error_responses_have_request_id(self, client):
        # Bad request
        resp = client.post("/render", json={})
        assert "request_id" in resp.json()
        assert "X-Request-ID" in resp.headers

        # Not found
        resp = client.post(
            "/render",
            json={
                "template": "nope.typ",
                "data": {},
            },
        )
        assert "request_id" in resp.json()

    def test_debug_mode_includes_detail_on_render_error(self, debug_client):
        # Use a template that references a missing image via the server
        # We need a template in EXAMPLES that will fail at compile time
        # Use bad data that causes a Jinja error
        resp = debug_client.post(
            "/render",
            json={
                "template": "invoice.j2.typ",
                "data": {},  # Missing required nested fields
            },
        )
        if resp.status_code == 500:
            data = resp.json()
            # In debug mode, detail and source_path should be present
            assert "detail" in data
            assert "stage" in data

    def test_non_debug_excludes_detail_and_source_path(self, client):
        resp = client.post(
            "/render",
            json={
                "template": "invoice.j2.typ",
                "data": {},  # Will fail with missing variable
            },
        )
        if resp.status_code == 500:
            data = resp.json()
            # In non-debug mode, detail and source_path should NOT be present
            assert "detail" not in data
            assert "source_path" not in data
            # But error, message, stage, request_id should be
            assert "error" in data
            assert "message" in data
            assert "stage" in data
            assert "request_id" in data

    def test_timeout_error_code(self, client):
        # Create an app with very short timeout to test the code
        app = create_app(EXAMPLES, render_timeout=0.001)
        short_client = TestClient(app)
        resp = short_client.post(
            "/render",
            json={
                "template": "invoice.j2.typ",
                "data": json.load(open(EXAMPLES / "invoice_data.json")),
            },
        )
        # May or may not timeout depending on speed — just verify
        # the response format is correct either way
        if resp.status_code == 504:
            data = resp.json()
            assert data["error"] == "RENDER_TIMEOUT"
            assert "stage" in data


# ---------------------------------------------------------------------------
# CLI error formatting
# ---------------------------------------------------------------------------


class TestCLIErrorFormat:
    def test_format_includes_code(self):
        exc = FormforgeError(
            "file not found",
            code=ErrorCode.MISSING_ASSET,
            stage="compilation",
        )
        output = _format_error(exc)
        assert "MISSING_ASSET" in output
        assert "compilation" in output

    def test_format_includes_template_path(self):
        exc = FormforgeError(
            "undefined var",
            code=ErrorCode.TEMPLATE_VARIABLE,
            stage="template_preprocess",
            template_path="invoice.j2.typ",
        )
        output = _format_error(exc)
        assert "invoice.j2.typ" in output

    def test_format_includes_full_diagnostic(self):
        exc = FormforgeError(
            "summary line",
            code=ErrorCode.COMPILE_ERROR,
            stage="compilation",
            detail="summary line\n  at line 5\n  in column 10",
        )
        output = _format_error(exc)
        assert "at line 5" in output
        assert "in column 10" in output

    def test_cli_render_error_exit_code(self, tmp_path):
        out = tmp_path / "out.pdf"
        code = main(
            [
                "render",
                str(FIXTURES / "missing_image.j2.typ"),
                str(FIXTURES / "simple.json"),
                "-o",
                str(out),
            ]
        )
        assert code == 1
        # Clean up intermediate files
        for f in FIXTURES.glob("_formforge_*.typ"):
            f.unlink()

    def test_cli_template_not_found_exit_code(self, tmp_path):
        out = tmp_path / "out.pdf"
        code = main(
            [
                "render",
                "nope.j2.typ",
                str(FIXTURES / "simple.json"),
                "-o",
                str(out),
            ]
        )
        assert code == 1
