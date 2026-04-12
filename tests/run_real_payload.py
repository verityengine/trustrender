#!/usr/bin/env python3
"""Real-payload harness for invoice ingestion.

Usage:
    # Run a single file:
    python tests/run_real_payload.py path/to/invoice.json

    # Paste JSON directly (reads stdin):
    echo '{"invoice_number": ...}' | python tests/run_real_payload.py -

    # Run all fixtures in tests/fixtures/real_invoices/:
    python tests/run_real_payload.py --all
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running from repo root without installing
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from trustrender.invoice_ingest import ingest_invoice


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "real_invoices"


def _classify_failure(report) -> str:
    """Classify the primary reason a blocked payload failed."""
    blocked = [e for e in report.errors if e.severity == "blocked"]

    # Arithmetic contradiction: payload had values that disagreed
    if any("arithmetic" in e.rule_id for e in blocked):
        return "arithmetic_contradiction"

    # Structural gap: data was present but not extracted
    # Heuristic: if there are many unknown fields AND missing identity fields,
    # it's likely a structural gap rather than truly absent data
    unknown_count = len(report.unknown_fields)
    identity_blocked = [e for e in blocked if e.rule_id.startswith("identity.")]

    if identity_blocked and unknown_count >= 3:
        return "structural_gap"

    # Missing data: sender/recipient/invoice_number genuinely absent
    return "missing_data"


def _summarize(name: str, data: dict) -> None:
    report = ingest_invoice(data)

    blocked = [e for e in report.errors if e.severity == "blocked"]
    errors = [e for e in report.errors if e.severity == "error"]

    print(f"\n{'─' * 60}")
    print(f"  {name}")
    print(f"{'─' * 60}")
    print(f"  status        : {report.status}")
    print(f"  render_ready  : {report.render_ready}")

    if blocked:
        print(f"  blocked ({len(blocked)})   :")
        for e in blocked:
            print(f"    [{e.rule_id}] {e.message}")

    if errors:
        print(f"  errors ({len(errors)})    :")
        for e in errors:
            print(f"    [{e.rule_id}] {e.message}")

    print(f"  warnings      : {len(report.warnings)}")
    print(f"  normalizations: {len(report.normalizations)}")
    print(f"  computed      : {report.computed_fields or '—'}")
    print(f"  unknown fields: {len(report.unknown_fields)}")

    if not report.render_ready:
        failure_type = _classify_failure(report)
        print(f"  failure_type  : {failure_type}")

    if report.unknown_fields:
        suspicious = [u for u in report.unknown_fields if u.classification == "suspicious"]
        near = [u for u in report.unknown_fields if u.classification == "near_match"]
        if near:
            print(f"  near_matches  : {[f'{u.path} → {u.suggestion}' for u in near]}")
        if suspicious:
            print(f"  suspicious    : {[u.path for u in suspicious]}")


def _load_file(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def main() -> None:
    args = sys.argv[1:]

    if not args or "--all" in args:
        if not FIXTURE_DIR.exists():
            print(f"No fixture directory at {FIXTURE_DIR}")
            sys.exit(1)
        files = sorted(FIXTURE_DIR.glob("*.json"))
        if not files:
            print(f"No JSON files in {FIXTURE_DIR}")
            sys.exit(1)
        print(f"Running {len(files)} real payload(s) from {FIXTURE_DIR.relative_to(Path.cwd())}/")
        for f in files:
            _summarize(f.stem, _load_file(f))

    elif args[0] == "-":
        data = json.load(sys.stdin)
        _summarize("stdin", data)

    else:
        path = Path(args[0])
        if not path.exists():
            print(f"File not found: {path}")
            sys.exit(1)
        _summarize(path.stem, _load_file(path))

    print()


if __name__ == "__main__":
    main()
