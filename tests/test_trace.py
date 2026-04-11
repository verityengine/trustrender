"""Tests for render lineage persistence."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from formforge import render
from formforge.errors import ErrorCode, FormforgeError
from formforge.trace import RenderTrace, StageTrace, TraceStore, init_store

EXAMPLES = Path(__file__).parent.parent / "examples"


@pytest.fixture
def store(tmp_path):
    """Create a temporary trace store for testing."""
    db_path = tmp_path / "test_history.db"
    return init_store(db_path)


@pytest.fixture
def _history_env(tmp_path, monkeypatch):
    """Set FORMFORGE_HISTORY for render() to pick up."""
    import formforge.trace as trace_mod

    db_path = tmp_path / "test_history.db"
    monkeypatch.setenv("FORMFORGE_HISTORY", str(db_path))
    # Reset global store so get_store() re-initializes from env
    trace_mod._store = None
    yield db_path
    trace_mod._store = None


class TestTraceStore:
    def test_record_and_query(self, store):
        trace = RenderTrace(
            template_name="test.j2.typ",
            outcome="success",
            total_ms=100,
            pdf_size=5000,
        )
        store.record(trace)
        results = store.query()
        assert len(results) == 1
        assert results[0].template_name == "test.j2.typ"
        assert results[0].outcome == "success"

    def test_query_by_template(self, store):
        store.record(RenderTrace(template_name="a.j2.typ", outcome="success"))
        store.record(RenderTrace(template_name="b.j2.typ", outcome="success"))
        results = store.query(template="a.j2.typ")
        assert len(results) == 1
        assert results[0].template_name == "a.j2.typ"

    def test_query_by_outcome(self, store):
        store.record(RenderTrace(template_name="t.j2.typ", outcome="success"))
        store.record(RenderTrace(template_name="t.j2.typ", outcome="error"))
        results = store.query(outcome="error")
        assert len(results) == 1
        assert results[0].outcome == "error"

    def test_stages_persisted(self, store):
        trace = RenderTrace(
            template_name="t.j2.typ",
            outcome="success",
            stages=[
                StageTrace(stage="compilation", status="pass", duration_ms=50),
                StageTrace(stage="provenance", status="pass", duration_ms=10),
            ],
        )
        store.record(trace)
        result = store.get(trace.id)
        assert result is not None
        assert len(result.stages) == 2
        assert result.stages[0].stage == "compilation"
        assert result.stages[1].stage == "provenance"

    def test_stats(self, store):
        store.record(RenderTrace(template_name="a.j2.typ", outcome="success", total_ms=100))
        store.record(RenderTrace(template_name="b.j2.typ", outcome="success", total_ms=200))
        store.record(RenderTrace(template_name="a.j2.typ", outcome="error", total_ms=10))
        stats = store.stats()
        assert stats["total"] == 3
        assert stats["successes"] == 2
        assert stats["failures"] == 1
        assert stats["unique_templates"] == 2

    def test_get_nonexistent(self, store):
        assert store.get("nonexistent-id") is None


class TestRenderWithTrace:
    def test_successful_render_traced(self, _history_env):
        from formforge.trace import get_store

        pdf = render("examples/invoice.j2.typ", "examples/invoice_data.json")
        assert pdf[:5] == b"%PDF-"

        store = get_store()
        traces = store.query()
        assert len(traces) == 1
        assert traces[0].outcome == "success"
        assert traces[0].template_name == "invoice.j2.typ"
        assert traces[0].pdf_size > 0
        assert traces[0].total_ms > 0
        # Should have compilation stage
        assert any(s.stage == "compilation" for s in traces[0].stages)

    def test_failed_render_traced(self, _history_env):
        from formforge.trace import get_store

        with pytest.raises(FormforgeError):
            render("examples/invoice.j2.typ", {}, validate=True)

        store = get_store()
        traces = store.query()
        assert len(traces) == 1
        assert traces[0].outcome == "error"
        assert traces[0].error_code == "DATA_CONTRACT"

    def test_zugferd_stages_traced(self, _history_env):
        from formforge.trace import get_store

        pdf = render(
            "examples/einvoice.j2.typ",
            "examples/einvoice_data.json",
            zugferd="en16931",
        )
        store = get_store()
        traces = store.query()
        assert len(traces) == 1
        stages = [s.stage for s in traces[0].stages]
        assert "zugferd_validation" in stages
        assert "compilation" in stages
        assert "zugferd_postprocess" in stages

    def test_provenance_traced(self, _history_env):
        from formforge.trace import get_store

        pdf = render(
            "examples/invoice.j2.typ",
            "examples/invoice_data.json",
            provenance=True,
        )
        store = get_store()
        traces = store.query()
        assert len(traces) == 1
        assert traces[0].provenance_hash != ""
        assert any(s.stage == "provenance" for s in traces[0].stages)

    def test_no_history_env_no_trace(self):
        """Without FORMFORGE_HISTORY, nothing is stored."""
        # Ensure env var is not set
        os.environ.pop("FORMFORGE_HISTORY", None)
        pdf = render("examples/invoice.j2.typ", "examples/invoice_data.json")
        assert pdf[:5] == b"%PDF-"
        # No store, no crash, no problem

    def test_output_hash_recorded(self, _history_env):
        """Successful render records a non-empty output SHA-256."""
        from formforge.trace import get_store

        render("examples/invoice.j2.typ", "examples/invoice_data.json")
        store = get_store()
        traces = store.query()
        assert len(traces) == 1
        assert traces[0].output_hash.startswith("sha256:")
        assert len(traces[0].output_hash) > 10

    def test_output_hash_stable(self, _history_env):
        """Same inputs produce the same output hash (deterministic render)."""
        from formforge.trace import get_store

        render("examples/invoice.j2.typ", "examples/invoice_data.json")
        render("examples/invoice.j2.typ", "examples/invoice_data.json")
        store = get_store()
        traces = store.query(limit=2)
        assert len(traces) == 2
        assert traces[0].output_hash == traces[1].output_hash
        assert traces[0].output_hash != ""

    def test_output_hash_changes_with_data(self, _history_env):
        """Different data produces a different output hash."""
        from formforge.trace import get_store

        render("examples/invoice.j2.typ", "examples/invoice_data.json")
        render("examples/receipt.j2.typ", "examples/receipt_data.json")
        store = get_store()
        traces = store.query(limit=2)
        assert len(traces) == 2
        assert traces[0].output_hash != traces[1].output_hash
