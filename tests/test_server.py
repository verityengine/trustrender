"""Tests for the HTTP server endpoints."""

import json
from pathlib import Path

import pytest
from starlette.testclient import TestClient

from typeset.server import create_app

EXAMPLES = Path("examples")


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
        assert "template" in resp.json()["error"]

    def test_missing_data(self, client):
        resp = client.post("/render", json={"template": "invoice.j2.typ"})
        assert resp.status_code == 400
        assert "data" in resp.json()["error"]

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
        assert "Unknown fields" in resp.json()["error"]

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
        assert "Invalid template path" in resp.json()["error"]

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
        assert "not found" in resp.json()["error"]

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
