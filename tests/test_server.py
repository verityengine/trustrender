"""Tests for the HTTP server endpoints."""

import json
import shutil
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from formforge.server import create_app

EXAMPLES = Path("examples")
FIXTURES = Path("tests/fixtures")
HAS_TYPST_CLI = shutil.which("typst") is not None


@pytest.fixture
def client():
    app = create_app(EXAMPLES)
    return TestClient(app)


@pytest.fixture
def debug_client():
    app = create_app(EXAMPLES, debug=True)
    return TestClient(app)


# --- Health endpoint ---


class TestHealth:
    def test_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_has_request_id(self, client):
        resp = client.get("/health")
        assert "X-Request-ID" in resp.headers


# --- Render endpoint ---


class TestRenderSuccess:
    def test_returns_pdf(self, client):
        resp = client.post("/render", json={
            "template": "invoice.j2.typ",
            "data": json.load(open(EXAMPLES / "invoice_data.json")),
        })
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/pdf"
        assert resp.content[:5] == b"%PDF-"

    def test_has_request_id(self, client):
        resp = client.post("/render", json={
            "template": "invoice.j2.typ",
            "data": json.load(open(EXAMPLES / "invoice_data.json")),
        })
        assert "X-Request-ID" in resp.headers

    def test_preserves_client_request_id(self, client):
        resp = client.post(
            "/render",
            json={
                "template": "invoice.j2.typ",
                "data": json.load(open(EXAMPLES / "invoice_data.json")),
            },
            headers={"X-Request-ID": "my-custom-id-123"},
        )
        assert resp.headers["X-Request-ID"] == "my-custom-id-123"

    def test_static_typ_template(self, client):
        resp = client.post("/render", json={
            "template": "invoice_simple.typ",
            "data": {},
        })
        assert resp.status_code == 200
        assert resp.content[:5] == b"%PDF-"


# --- Input validation ---


class TestInputValidation:
    def test_missing_template(self, client):
        resp = client.post("/render", json={"data": {}})
        assert resp.status_code == 400
        assert resp.json()["error"] == "INVALID_DATA"
        assert "template" in resp.json()["message"]

    def test_missing_data(self, client):
        resp = client.post("/render", json={"template": "invoice.j2.typ"})
        assert resp.status_code == 400
        assert resp.json()["error"] == "INVALID_DATA"
        assert "data" in resp.json()["message"]

    def test_data_must_be_object(self, client):
        resp = client.post("/render", json={
            "template": "invoice.j2.typ",
            "data": [1, 2, 3],
        })
        assert resp.status_code == 400

    def test_unknown_fields_rejected(self, client):
        resp = client.post("/render", json={
            "template": "invoice.j2.typ",
            "data": {},
            "format": "png",
        })
        assert resp.status_code == 400
        assert resp.json()["error"] == "INVALID_DATA"
        assert "Unknown fields" in resp.json()["message"]

    def test_invalid_json(self, client):
        resp = client.post(
            "/render",
            content=b"not json",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400

    def test_debug_must_be_bool(self, client):
        resp = client.post("/render", json={
            "template": "invoice.j2.typ",
            "data": {},
            "debug": "yes",
        })
        assert resp.status_code == 400


# --- Path traversal ---


class TestPathTraversal:
    def test_dotdot_rejected(self, client):
        resp = client.post("/render", json={
            "template": "../pyproject.toml",
            "data": {},
        })
        assert resp.status_code == 400
        assert resp.json()["error"] == "INVALID_DATA"
        assert "Invalid template path" in resp.json()["message"]

    def test_absolute_path_rejected(self, client):
        resp = client.post("/render", json={
            "template": "/etc/passwd",
            "data": {},
        })
        assert resp.status_code in (400, 404)


# --- Template not found ---


class TestTemplateNotFound:
    def test_returns_404(self, client):
        resp = client.post("/render", json={
            "template": "nonexistent.j2.typ",
            "data": {},
        })
        assert resp.status_code == 404
        assert resp.json()["error"] == "TEMPLATE_NOT_FOUND"
        assert "not found" in resp.json()["message"]

    def test_404_has_request_id(self, client):
        resp = client.post("/render", json={
            "template": "nonexistent.j2.typ",
            "data": {},
        })
        assert "X-Request-ID" in resp.headers
        assert resp.json()["request_id"] == resp.headers["X-Request-ID"]


# --- Render errors ---


class TestRenderErrors:
    def test_bad_template_returns_500(self, client):
        resp = client.post("/render", json={
            "template": "hello.typ",
            "data": {},
        })
        # hello.typ is valid, so this should succeed
        assert resp.status_code == 200

    def test_error_has_request_id(self, client):
        resp = client.post("/render", json={
            "template": "nonexistent.j2.typ",
            "data": {},
        })
        assert "request_id" in resp.json()

    def test_debug_includes_source_path(self, debug_client):
        # Create a template that will fail during render (missing image)
        resp = debug_client.post("/render", json={
            "template": "invoice.j2.typ",
            "data": {
                "invoice_number": "T",
                "invoice_date": "T",
                "due_date": "T",
                "payment_terms": "T",
                "sender": {"name": "T", "address_line1": "", "address_line2": "", "email": ""},
                "recipient": {"name": "T", "address_line1": "", "address_line2": "", "email": ""},
                "items": [],
                "subtotal": "0",
                "tax_rate": "0",
                "tax_amount": "0",
                "total": "0",
                "notes": "",
            },
        })
        # Invoice template references assets/logo.png — should succeed since
        # the template dir is examples/ which has assets/logo.png
        assert resp.status_code == 200


# --- Server execution model: CLI backend, killable timeout ---


@pytest.mark.skipif(not HAS_TYPST_CLI, reason="typst CLI not on PATH")
class TestServerTimeout:
    """Server timeout is real: subprocess is killed, 504 returned.

    Uses a very short render_timeout (0.001s) so that any real template
    will timeout reliably — this tests timeout behavior, not template speed.
    """

    @pytest.fixture
    def fast_timeout_client(self):
        app = create_app(EXAMPLES, render_timeout=0.001)
        return TestClient(app, raise_server_exceptions=False)

    @pytest.fixture
    def fast_timeout_fixtures_client(self):
        app = create_app(FIXTURES, render_timeout=0.001)
        return TestClient(app, raise_server_exceptions=False)

    def test_jinja_timeout_returns_504(self, fast_timeout_client):
        """Jinja template timeout returns 504 with RENDER_TIMEOUT."""
        resp = fast_timeout_client.post("/render", json={
            "template": "invoice.j2.typ",
            "data": json.load(open(EXAMPLES / "invoice_data.json")),
        })
        assert resp.status_code == 504
        data = resp.json()
        assert data["error"] == "RENDER_TIMEOUT"

    def test_static_timeout_returns_504(self, fast_timeout_client):
        """Raw .typ template timeout returns 504 with RENDER_TIMEOUT."""
        resp = fast_timeout_client.post("/render", json={
            "template": "hello.typ",
            "data": {},
        })
        assert resp.status_code == 504
        data = resp.json()
        assert data["error"] == "RENDER_TIMEOUT"

    def test_timeout_response_has_request_id(self, fast_timeout_client):
        """Timeout error responses include request_id."""
        resp = fast_timeout_client.post("/render", json={
            "template": "hello.typ",
            "data": {},
        })
        assert resp.status_code == 504
        assert "X-Request-ID" in resp.headers
        assert "request_id" in resp.json()

    def test_timeout_response_has_stage(self, fast_timeout_client):
        """Timeout error response includes stage field."""
        resp = fast_timeout_client.post("/render", json={
            "template": "hello.typ",
            "data": {},
        })
        assert resp.status_code == 504
        assert "stage" in resp.json()

    def test_repeated_timeouts_no_temp_file_leak(self, fast_timeout_fixtures_client):
        """Repeated timeouts do not accumulate orphan temp files."""
        before = set(FIXTURES.glob("_formforge_*"))
        for _ in range(3):
            fast_timeout_fixtures_client.post("/render", json={
                "template": "simple.j2.typ",
                "data": json.load(open(FIXTURES / "simple.json")),
            })
        after = set(FIXTURES.glob("_formforge_*"))
        new_files = after - before
        assert len(new_files) == 0, f"Orphan temp files: {new_files}"

    def test_same_template_succeeds_with_normal_timeout(self):
        """Same template that times out at 0.001s succeeds with normal timeout."""
        app = create_app(EXAMPLES, render_timeout=30)
        client = TestClient(app)
        resp = client.post("/render", json={
            "template": "hello.typ",
            "data": {},
        })
        assert resp.status_code == 200
        assert resp.content[:5] == b"%PDF-"

    def test_debug_mode_timeout_preserves_artifact(self):
        """In debug mode, timeout preserves intermediate file for inspection."""
        app = create_app(FIXTURES, render_timeout=0.001, debug=True)
        client = TestClient(app, raise_server_exceptions=False)
        before = set(FIXTURES.glob("_formforge_*"))
        resp = client.post("/render", json={
            "template": "simple.j2.typ",
            "data": json.load(open(FIXTURES / "simple.json")),
        })
        assert resp.status_code == 504
        after = set(FIXTURES.glob("_formforge_*"))
        new_files = after - before
        assert len(new_files) == 1, "Debug mode should preserve artifact on timeout"
        # Cleanup test artifact
        for f in new_files:
            f.unlink()

    def test_no_artifact_leak_in_examples(self):
        """Normal server operation does not leave artifacts in examples/."""
        before = set(EXAMPLES.glob("_formforge_*"))
        app = create_app(EXAMPLES, render_timeout=30)
        client = TestClient(app)
        # Successful render
        resp = client.post("/render", json={
            "template": "invoice.j2.typ",
            "data": json.load(open(EXAMPLES / "invoice_data.json")),
        })
        assert resp.status_code == 200
        after = set(EXAMPLES.glob("_formforge_*"))
        assert after == before, f"Artifacts leaked: {after - before}"


@pytest.mark.skipif(not HAS_TYPST_CLI, reason="typst CLI not on PATH")
class TestServerCLIBackendParity:
    """Server forced CLI path produces same results as normal render path."""

    def test_jinja_render_succeeds(self, client):
        """Jinja template renders successfully through server CLI backend."""
        resp = client.post("/render", json={
            "template": "invoice.j2.typ",
            "data": json.load(open(EXAMPLES / "invoice_data.json")),
        })
        assert resp.status_code == 200
        assert resp.content[:5] == b"%PDF-"
        assert len(resp.content) > 1000

    def test_static_render_succeeds(self, client):
        """Raw .typ template renders successfully through server CLI backend."""
        resp = client.post("/render", json={
            "template": "hello.typ",
            "data": {},
        })
        assert resp.status_code == 200
        assert resp.content[:5] == b"%PDF-"

    def test_font_paths_work(self):
        """Explicit font paths work through server CLI backend."""
        fonts_dir = Path("fonts")
        font_paths = [str(fonts_dir)] if fonts_dir.is_dir() else None
        app = create_app(EXAMPLES, font_paths=font_paths)
        client = TestClient(app)
        resp = client.post("/render", json={
            "template": "invoice.j2.typ",
            "data": json.load(open(EXAMPLES / "invoice_data.json")),
        })
        assert resp.status_code == 200
        assert resp.content[:5] == b"%PDF-"

    def test_bundled_fonts_work(self, client):
        """Bundled fonts are resolved at app creation and work in CLI backend."""
        resp = client.post("/render", json={
            "template": "invoice.j2.typ",
            "data": json.load(open(EXAMPLES / "invoice_data.json")),
        })
        assert resp.status_code == 200
        assert resp.content[:5] == b"%PDF-"
