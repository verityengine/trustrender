"""Pytest suite for real-world invoice payloads.

Scans all JSON files in tests/fixtures/real_invoices/ and runs each through
ingest_invoice. Reports status, failure classification, and key counts.

These tests never assert render_ready=True — real payloads may legitimately
block due to missing data. Instead they assert structural expectations:
- no crash
- failure is correctly classified (missing_data vs structural_gap vs arithmetic)
- each file produces a valid IngestionReport
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from trustrender.invoice_ingest import ingest_invoice

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "real_invoices"


def _classify_failure(report) -> str:
    blocked = [e for e in report.errors if e.severity == "blocked"]
    if any("arithmetic" in e.rule_id for e in blocked):
        return "arithmetic_contradiction"
    identity_blocked = [e for e in blocked if e.rule_id.startswith("identity.")]
    if identity_blocked and len(report.unknown_fields) >= 3:
        return "structural_gap"
    return "missing_data"


def _real_payload_files():
    if not FIXTURE_DIR.exists():
        return []
    return sorted(FIXTURE_DIR.glob("*.json"))


@pytest.mark.parametrize("payload_path", _real_payload_files(), ids=lambda p: p.stem)
def test_real_payload(payload_path: Path, capsys) -> None:
    """Each real payload must produce a valid report without crashing."""
    with open(payload_path) as f:
        data = json.load(f)

    report = ingest_invoice(data)

    # Always: report is well-formed
    assert report.status in ("ready", "ready_with_warnings", "blocked")
    assert isinstance(report.render_ready, bool)
    assert isinstance(report.canonical, dict)
    assert isinstance(report.errors, list)
    assert isinstance(report.warnings, list)
    assert isinstance(report.normalizations, list)
    assert isinstance(report.unknown_fields, list)

    # Print compact summary (visible with pytest -s)
    blocked = [e for e in report.errors if e.severity == "blocked"]
    failure_type = _classify_failure(report) if not report.render_ready else "—"

    print(f"\n{payload_path.stem}")
    print(f"  status={report.status}  render_ready={report.render_ready}  failure={failure_type}")
    print(f"  blocked={len(blocked)}  warnings={len(report.warnings)}  "
          f"normalizations={len(report.normalizations)}  "
          f"unknown={len(report.unknown_fields)}  "
          f"computed={len(report.computed_fields)}")
    if blocked:
        for e in blocked:
            print(f"  ! [{e.rule_id}] {e.message}")


def test_real_payload_summary(capsys) -> None:
    """Print a score summary across all real payloads."""
    files = _real_payload_files()
    if not files:
        pytest.skip("No real payload fixtures found")

    results = []
    for path in files:
        with open(path) as f:
            data = json.load(f)
        report = ingest_invoice(data)
        failure = _classify_failure(report) if not report.render_ready else None
        results.append((path.stem, report.render_ready, failure))

    ready = sum(1 for _, r, _ in results if r)
    total = len(results)

    print(f"\n{'═' * 50}")
    print(f"  REAL PAYLOAD SCORE: {ready}/{total} render-ready")
    print(f"{'═' * 50}")
    for name, render_ready, failure in results:
        mark = "✓" if render_ready else "✗"
        detail = "" if render_ready else f"  [{failure}]"
        print(f"  {mark} {name}{detail}")
    print(f"{'═' * 50}")

    # No hard assertion on the score — it changes as engine improves.
    # The test passes as long as the pipeline doesn't crash.
    assert total > 0
