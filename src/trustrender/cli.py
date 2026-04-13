"""CLI entry point for TrustRender."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from . import AuditResult, TrustRenderError, __version__, audit, render


# ---------------------------------------------------------------------------
# Shared argument factories
# ---------------------------------------------------------------------------


def _add_font_path(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--font-path",
        action="append",
        dest="font_paths",
        help="Additional font directory (can be repeated)",
    )


def _add_validate(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--no-validate",
        action="store_false",
        dest="validate",
        help="Skip data contract validation before rendering",
    )
    parser.set_defaults(validate=True)


def _add_zugferd(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--zugferd",
        choices=["en16931"],
        help="Generate ZUGFeRD-compliant PDF (EN 16931)",
    )


def _add_provenance(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--provenance",
        action="store_true",
        help="Embed cryptographic generation proof in PDF metadata",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="trustrender",
        description="Generate PDFs from structured data. No browser required.",
    )
    parser.add_argument("--version", action="version", version=f"trustrender {__version__}")

    sub = parser.add_subparsers(dest="command")

    render_cmd = sub.add_parser("render", help="Render a template to PDF")
    render_cmd.add_argument("template", help="Path to template (.j2.typ or .typ)")
    render_cmd.add_argument("data", help="Path to JSON data file (use '-' for stdin)")
    render_cmd.add_argument("-o", "--output", required=True, help="Output PDF path")
    render_cmd.add_argument(
        "--debug",
        action="store_true",
        help="Preserve intermediate .typ file after rendering",
    )
    _add_font_path(render_cmd)
    _add_validate(render_cmd)
    _add_zugferd(render_cmd)
    _add_provenance(render_cmd)

    check_cmd = sub.add_parser("check", help="Inspect or validate template data contract")
    check_cmd.add_argument("template", help="Path to .j2.typ template")
    check_cmd.add_argument("--data", help="Path to JSON data file to validate against")

    serve_cmd = sub.add_parser("serve", help="Start HTTP render server")
    serve_cmd.add_argument(
        "--templates",
        default=os.environ.get("TRUSTRENDER_TEMPLATES_DIR"),
        help="Template directory root (or set TRUSTRENDER_TEMPLATES_DIR env var)",
    )
    serve_cmd.add_argument(
        "--port", type=int, default=8190, help="Port to listen on (default: 8190)"
    )
    serve_cmd.add_argument(
        "--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)"
    )
    serve_cmd.add_argument("--debug", action="store_true", help="Enable debug mode")
    _add_font_path(serve_cmd)
    serve_cmd.add_argument(
        "--render-timeout",
        type=float,
        default=30,
        help="Maximum seconds per render request (default: 30)",
    )
    serve_cmd.add_argument(
        "--max-concurrent",
        type=int,
        default=8,
        help="Maximum simultaneous render operations; excess gets 503 (default: 8)",
    )
    serve_cmd.add_argument(
        "--dashboard",
        action="store_true",
        help="Enable read-only dashboard at /dashboard",
    )
    serve_cmd.add_argument(
        "--history",
        help="Path to SQLite history database (enables render tracing)",
    )
    serve_cmd.add_argument(
        "--max-body-size",
        type=int,
        default=None,
        help="Maximum request body size in bytes (default: 10485760 = 10 MB, or set TRUSTRENDER_MAX_BODY_SIZE)",
    )
    serve_cmd.add_argument(
        "--cors-origin",
        action="append",
        default=[],
        dest="cors_origins",
        help="Allowed CORS origin (repeatable; also set TRUSTRENDER_CORS_ORIGINS as comma-separated list)",
    )

    preflight_cmd = sub.add_parser("preflight", help="Pre-render readiness verification")
    preflight_cmd.add_argument("template", help="Path to template (.j2.typ or .typ)")
    preflight_cmd.add_argument("data", help="Path to JSON data file")
    preflight_cmd.add_argument(
        "--zugferd",
        choices=["en16931"],
        help="Check compliance eligibility for this profile",
    )
    preflight_cmd.add_argument(
        "--semantic",
        action="store_true",
        help="Run semantic validation (arithmetic, dates, completeness)",
    )
    preflight_cmd.add_argument(
        "--strict",
        action="store_true",
        help="Block on partial contracts from unresolved dynamic includes",
    )
    _add_font_path(preflight_cmd)

    audit_cmd = sub.add_parser("audit", help="Render with full audit trail")
    audit_cmd.add_argument("template", help="Path to template (.j2.typ or .typ)")
    audit_cmd.add_argument("data", help="Path to JSON data file")
    audit_cmd.add_argument("-o", "--output", help="Output PDF path")
    audit_cmd.add_argument(
        "--baseline-dir",
        help="Baseline directory for drift detection",
    )
    audit_cmd.add_argument(
        "--save-baseline",
        action="store_true",
        help="Save current render as new baseline",
    )
    audit_cmd.add_argument(
        "--semantic",
        action="store_true",
        help="Run semantic validation (arithmetic, dates, completeness)",
    )
    _add_validate(audit_cmd)
    _add_font_path(audit_cmd)
    _add_zugferd(audit_cmd)
    _add_provenance(audit_cmd)
    audit_cmd.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output audit result as JSON",
    )

    baseline_cmd = sub.add_parser("baseline", help="Manage render baselines")
    baseline_sub = baseline_cmd.add_subparsers(dest="baseline_action")

    baseline_save = baseline_sub.add_parser("save", help="Save a new baseline")
    baseline_save.add_argument("template", help="Path to template")
    baseline_save.add_argument("data", help="Path to JSON data file")
    baseline_save.add_argument(
        "--baseline-dir",
        required=True,
        help="Baseline directory",
    )
    _add_font_path(baseline_save)
    _add_validate(baseline_save)
    _add_zugferd(baseline_save)
    _add_provenance(baseline_save)

    baseline_check = baseline_sub.add_parser("check", help="Check against baseline")
    baseline_check.add_argument("template", help="Path to template")
    baseline_check.add_argument("data", help="Path to JSON data file")
    baseline_check.add_argument(
        "--baseline-dir",
        required=True,
        help="Baseline directory",
    )
    _add_font_path(baseline_check)
    _add_validate(baseline_check)
    _add_zugferd(baseline_check)
    _add_provenance(baseline_check)

    history_cmd = sub.add_parser("history", help="View render history and lineage")
    history_cmd.add_argument("--template", help="Filter by template name")
    history_cmd.add_argument("--failures", action="store_true", help="Show only failures")
    history_cmd.add_argument("--stats", action="store_true", help="Show aggregate statistics")
    history_cmd.add_argument("--json", action="store_true", dest="as_json", help="Output as JSON")
    history_cmd.add_argument("-n", "--limit", type=int, default=20, help="Number of records")

    trace_cmd = sub.add_parser("trace", help="Show detailed trace for a render")
    trace_cmd.add_argument("trace_id", help="Render trace ID")

    doctor_cmd = sub.add_parser("doctor", help="Check environment and diagnose issues")
    doctor_cmd.add_argument(
        "--smoke",
        action="store_true",
        help="Run a quick render and server health smoke test",
    )

    ingest_cmd = sub.add_parser("ingest", help="Normalize messy invoice JSON into canonical payload")
    ingest_cmd.add_argument("data", help="Path to JSON data file (use '-' for stdin)")
    ingest_cmd.add_argument("-o", "--output", help="Write canonical payload to file instead of stdout")
    ingest_cmd.add_argument("--quiet", action="store_true", help="Suppress summary, output JSON only")

    sub.add_parser("quickstart", help="Demo the ingest-to-render pipeline on real-world invoice data")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        print()
        print("  Get started:  trustrender quickstart")
        print()
        return 1

    if args.command == "quickstart":
        return _run_quickstart()

    if args.command == "ingest":
        return _run_ingest(args)

    if args.command == "render":
        return _run_render(args)

    if args.command == "check":
        return _run_check(args)

    if args.command == "preflight":
        return _run_preflight(args)

    if args.command == "audit":
        return _run_audit(args)

    if args.command == "baseline":
        return _run_baseline(args)

    if args.command == "history":
        return _run_history(args)

    if args.command == "trace":
        return _run_trace(args)

    if args.command == "serve":
        return _run_serve(args)

    if args.command == "doctor":
        from .doctor import run_doctor

        return run_doctor(smoke=args.smoke)

    return 1


def _run_ingest(args: argparse.Namespace) -> int:
    """Run the ingest pipeline on messy invoice JSON."""
    import json

    from .invoice_ingest import ingest_invoice

    try:
        if args.data == "-":
            raw = json.load(sys.stdin)
        else:
            with open(args.data) as f:
                raw = json.load(f)
    except json.JSONDecodeError as exc:
        print(f"error: invalid JSON: {exc}", file=sys.stderr)
        return 1
    except FileNotFoundError:
        print(f"error: file not found: {args.data}", file=sys.stderr)
        return 1

    report = ingest_invoice(raw)

    # Summary to stderr (unless --quiet)
    if not args.quiet:
        _print_ingest_summary(report, verbose=True)

    # Output JSON to stdout or file
    payload = report.template_payload if report.render_ready else report.canonical
    output_json = json.dumps(payload, indent=2, ensure_ascii=False)

    if args.output:
        Path(args.output).write_text(output_json + "\n")
        if not args.quiet:
            print(f"\n  Wrote: {args.output}", file=sys.stderr)
    else:
        print(output_json)

    return 0 if report.render_ready else 1


def _print_ingest_summary(report, verbose: bool = False) -> None:
    """Print a human-readable ingest summary to stderr."""
    err = lambda s="": print(s, file=sys.stderr)

    aliases = [n for n in report.normalizations if n.source == "alias"]
    computed = [n for n in report.normalizations if n.source == "computed"]
    coerced = [n for n in report.normalizations if n.source not in ("alias", "computed", "exact", "missing")]

    if verbose:
        # Full list — for standalone `trustrender ingest`
        for n in aliases:
            orig = n.original_key or "?"
            err(f"  \u2713 {n.canonical_name} \u2190 {orig}")
        for n in computed:
            err(f"  \u2713 {n.canonical_name} (computed)")
    else:
        # Compact — show top-level aliases only, skip per-item repeats
        seen_patterns = set()
        for n in aliases:
            # Collapse items[0].field, items[1].field into one line
            canon = n.canonical_name
            if "[" in canon:
                pattern = canon.split("]", 1)[-1] if "]" in canon else canon
                orig = n.original_key or "?"
                key = (pattern, orig)
                if key in seen_patterns:
                    continue
                seen_patterns.add(key)
                err(f"  \u2713 items[*]{pattern} \u2190 {orig}")
            else:
                orig = n.original_key or "?"
                err(f"  \u2713 {canon} \u2190 {orig}")
        if computed:
            err(f"  \u2713 {len(computed)} field{'s' if len(computed) != 1 else ''} computed (line_total, subtotal, ...)")

    # Errors — always show in full
    for e in report.errors:
        severity = "BLOCKED" if e.severity == "blocked" else "ERROR"
        err(f"  \u2717 {severity}: {e.message}")

    for w in report.warnings:
        err(f"  ! {w.message}")

    # Status line
    alias_count = len(aliases)
    coerce_count = len(coerced)
    computed_count = len(computed)
    parts = []
    if alias_count:
        parts.append(f"{alias_count} alias{'es' if alias_count != 1 else ''}")
    if coerce_count:
        parts.append(f"{coerce_count} coercion{'s' if coerce_count != 1 else ''}")
    if computed_count:
        parts.append(f"{computed_count} computed")

    detail = f" ({', '.join(parts)})" if parts else ""

    if report.render_ready:
        err(f"\n  Status: ready{detail}")
    else:
        err_count = len(report.errors)
        err(f"\n  Status: blocked ({err_count} error{'s' if err_count != 1 else ''}){detail}")


def _run_quickstart() -> int:
    """Demo the ingest-to-render pipeline on real-world invoice data."""
    import json
    import shutil

    from .invoice_ingest import ingest_invoice

    outdir = Path("trustrender-quickstart")
    if outdir.exists():
        print(f"error: {outdir}/ already exists. Remove it or use a different directory.", file=sys.stderr)
        return 1

    # Copy sample data from fixtures
    fixtures_dir = Path(__file__).parent.parent.parent / "tests" / "fixtures"
    examples_dir = fixtures_dir / "examples"
    real_dir = fixtures_dir / "real_invoices"

    # Build sample files — use embedded copies if fixture files aren't available (pip install case)
    outdir.mkdir()

    qb_data = _load_sample(real_dir / "quickbooks_raw.json", _QUICKBOOKS_SAMPLE)
    stripe_data = _load_sample(real_dir / "stripe_raw.json", _STRIPE_SAMPLE)
    broken_data = _load_sample(examples_dir / "broken_invoice.json", _BROKEN_SAMPLE)

    (outdir / "quickbooks_invoice.json").write_text(json.dumps(qb_data, indent=2) + "\n")
    (outdir / "stripe_invoice.json").write_text(json.dumps(stripe_data, indent=2) + "\n")
    (outdir / "broken_invoice.json").write_text(json.dumps(broken_data, indent=2) + "\n")

    err = lambda s="": print(s, file=sys.stderr)

    err()
    err(f"  Created {outdir}/")
    err(f"    quickbooks_invoice.json")
    err(f"    stripe_invoice.json")
    err(f"    broken_invoice.json")

    # --- Step 1: Ingest the QuickBooks sample ---
    err()
    err("  \u2500\u2500 Ingesting QuickBooks invoice \u2500\u2500")
    err()
    qb_report = ingest_invoice(qb_data)
    _print_ingest_summary(qb_report)

    if qb_report.render_ready and qb_report.template_payload:
        # Render to PDF
        err()
        err("  \u2500\u2500 Rendering invoice.pdf \u2500\u2500")
        try:
            from . import render

            template_dir = Path(__file__).parent / "builtin_templates"
            template_path = template_dir / "invoice.j2.typ"
            output_path = outdir / "invoice.pdf"

            pdf_bytes = render(
                str(template_path),
                qb_report.template_payload,
                output=str(output_path),
            )
            err(f"  Rendered {len(pdf_bytes):,} bytes \u2192 {output_path}")
        except Exception as exc:
            err(f"  Render failed: {exc}")

    # --- Step 2: Show the broken sample blocking ---
    err()
    err("  \u2500\u2500 Ingesting broken invoice (should block) \u2500\u2500")
    err()
    broken_report = ingest_invoice(broken_data)
    _print_ingest_summary(broken_report)

    # --- Done ---
    err()
    err(f"  Done.")
    if (outdir / "invoice.pdf").exists():
        err(f"  Open {outdir}/invoice.pdf to see the result.")
    err(f"  Run: trustrender ingest {outdir}/stripe_invoice.json")
    err()

    return 0


def _load_sample(fixture_path: Path, fallback: dict) -> dict:
    """Load from fixture file if available, otherwise use embedded fallback."""
    import json

    if fixture_path.exists():
        with open(fixture_path) as f:
            return json.load(f)
    return fallback


# Embedded sample data for pip-installed case (no test fixtures available)
_QUICKBOOKS_SAMPLE = {
    "DocNumber": "INV-1089",
    "TxnDate": "2026-03-10",
    "DueDate": "2026-04-09",
    "CompanyName": "Redwood Digital LLC",
    "CompanyEmail": "ar@redwood-digital.com",
    "customer": {
        "Name": "Pinnacle Group",
        "EmailAddress": "billing@pinnaclegroup.com",
        "BillingAddress": "200 Corporate Plaza, Chicago, IL 60601",
    },
    "Line": [
        {"LineNum": 1, "Description": "UX/UI Design — Phase 1", "Quantity": 1, "UnitPrice": 3500.00, "Amount": 3500.00},
        {"LineNum": 2, "Description": "Frontend Development", "Quantity": 40, "UnitPrice": 95.00, "Amount": 3800.00},
        {"LineNum": 3, "Description": "Project Management", "Quantity": 8, "UnitPrice": 120.00, "Amount": 960.00},
    ],
    "SubTotal": 8260.00,
    "TotalTax": 702.10,
    "taxRate": "8.5%",
    "TotalAmt": 8962.10,
    "CustomerMemo": "Payment due within 30 days of invoice date.",
    "paymentTerms": "Net 30",
}

_STRIPE_SAMPLE = {
    "number": "INV-2026-00042",
    "date": "2026-03-01",
    "due_date": "2026-03-31",
    "account_name": "Buildspace Labs Inc.",
    "account_email": "billing@buildspace.so",
    "customer_name": "Momentum Ventures",
    "customer_email": "finance@momentum.vc",
    "lines": {
        "data": [
            {"title": "Platform subscription (Pro)", "count": 1, "price": 399.00, "amount": 399.00},
            {"title": "API calls overage (50K)", "count": 1, "price": 45.00, "amount": 45.00},
            {"title": "Priority support (monthly)", "count": 1, "price": 149.00, "amount": 149.00},
        ]
    },
    "sub_total": 593.00,
    "tax": 50.41,
    "taxRate": "8.5%",
    "grand_total": 643.41,
    "currency": "usd",
}

_BROKEN_SAMPLE = {
    "invoice_date": "2026-03-15",
    "due_date": "2026-04-14",
    "sender": {"name": "Acme Corp", "address": "123 Main St", "email": "billing@acme.com"},
    "recipient": {"name": "Acme Corp", "address": "123 Main St", "email": "billing@acme.com"},
    "items": [
        {"description": "Consulting services", "quantity": 10, "unit_price": 150.00, "line_total": 500.00},
    ],
    "subtotal": 1500.00,
    "tax_rate": 8.5,
    "tax_amount": 127.50,
    "total": 1627.50,
}


def _run_history(args: argparse.Namespace) -> int:
    from .trace import get_store

    store = get_store()
    if not store:
        print(
            "error: History not enabled. Set TRUSTRENDER_HISTORY=~/.trustrender/history.db",
            file=sys.stderr,
        )
        return 1

    if args.stats:
        stats = store.stats()
        print(f"Total renders:      {stats['total']}")
        print(f"Successes:          {stats['successes']}")
        print(f"Failures:           {stats['failures']}")
        print(f"Success rate:       {stats['success_rate']}%")
        print(f"Avg render time:    {stats['avg_ms']}ms")
        print(f"Unique templates:   {stats['unique_templates']}")
        return 0

    outcome = "error" if args.failures else None
    traces = store.query(template=args.template, outcome=outcome, limit=args.limit)

    if not traces:
        print("No render history found.")
        return 0

    if args.as_json:
        import json

        print(json.dumps([t.to_dict() for t in traces], indent=2))
        return 0

    # Table output
    print(f"{'TIME':<22} {'TEMPLATE':<28} {'RESULT':<8} {'SIZE':<10} {'DURATION'}")
    print("-" * 80)
    for t in traces:
        time_str = t.timestamp[:19].replace("T", " ")
        result = "OK" if t.outcome == "success" else "FAIL"
        size = f"{t.pdf_size // 1024}KB" if t.pdf_size else "--"
        duration = f"{t.total_ms}ms"
        print(f"{time_str:<22} {t.template_name:<28} {result:<8} {size:<10} {duration}")
        if t.outcome == "error":
            print(f"  > {t.error_code} at {t.error_stage}: {t.error_message[:60]}")

    return 0


def _run_trace(args: argparse.Namespace) -> int:
    from .trace import get_store

    store = get_store()
    if not store:
        print(
            "error: History not enabled. Set TRUSTRENDER_HISTORY=~/.trustrender/history.db",
            file=sys.stderr,
        )
        return 1

    trace = store.get(args.trace_id)
    if not trace:
        print(f"error: Trace not found: {args.trace_id}", file=sys.stderr)
        return 1

    print(f"Trace:     {trace.id}")
    print(f"Time:      {trace.timestamp}")
    print(f"Template:  {trace.template_name}")
    print(f"Outcome:   {trace.outcome.upper()}")
    if trace.error_code:
        print(f"Error:     {trace.error_code} at {trace.error_stage}")
        print(f"Message:   {trace.error_message}")
    print(f"Duration:  {trace.total_ms}ms")
    if trace.pdf_size:
        print(f"PDF size:  {trace.pdf_size // 1024}KB")
    if trace.zugferd_profile:
        print(f"ZUGFeRD:   {trace.zugferd_profile}")
    if trace.provenance_hash:
        print(f"Provenance: {trace.provenance_hash[:40]}...")
    print()

    print("STAGES:")
    for s in trace.stages:
        marker = "✓" if s.status == "pass" else "✗" if s.status in ("fail", "error") else "○"
        meta = ""
        if s.metadata:
            if "pdf_size" in s.metadata:
                meta = f" ({s.metadata['pdf_size'] // 1024}KB)"
            elif "xml_size" in s.metadata:
                meta = f" ({s.metadata['xml_size']} bytes XML)"
            elif "profile" in s.metadata:
                meta = f" ({s.metadata['profile']})"
        print(f"  {marker} {s.stage:<24} {s.status:<6} {s.duration_ms}ms{meta}")
        for err in s.errors:
            print(f"      {err['path']}: {err['message']}")

    return 0


def _resolve_hints(template_name: str):
    """Auto-detect semantic hints based on template name."""
    from .semantic import resolve_hints

    return resolve_hints(template_name)


def _run_audit(args: argparse.Namespace) -> int:
    """Render with full audit: fingerprint, drift, semantic."""
    import json as json_mod

    template_path = Path(args.template)
    data_path = Path(args.data)

    if not data_path.exists():
        print(f"error: Data file not found: {data_path}", file=sys.stderr)
        return 1

    with open(data_path) as f:
        data = json_mod.load(f)

    semantic_hints = _resolve_hints(template_path.name) if args.semantic else None
    if args.semantic and semantic_hints is None:
        print(
            f"warning: no semantic hints configured for '{template_path.name}'"
            " — skipping semantic checks",
            file=sys.stderr,
        )

    try:
        result = audit(
            template_path,
            data,
            output=args.output,
            font_paths=args.font_paths,
            validate=args.validate,
            zugferd=args.zugferd,
            provenance=args.provenance,
            baseline_dir=args.baseline_dir,
            save_baseline=args.save_baseline,
            semantic_hints=semantic_hints,
        )
    except TrustRenderError as exc:
        print(_format_error(exc), file=sys.stderr)
        return 1

    if args.as_json:
        report = {
            "fingerprint": result.fingerprint.to_dict(),
            "change_set": result.change_set.to_dict() if result.change_set else None,
            "drift_result": result.drift_result.to_dict() if result.drift_result else None,
            "semantic_report": result.semantic_report.to_dict() if result.semantic_report else None,
            "pdf_size": len(result.pdf_bytes),
        }
        print(json_mod.dumps(report, indent=2))
        return 0

    # Human-readable output
    fp = result.fingerprint
    print(f"Audit: {template_path.name}")
    print(f"  Fingerprint: {fp.fingerprint[:40]}...")
    print(f"  PDF size: {len(result.pdf_bytes):,} bytes")
    if args.output:
        print(f"  Output: {args.output}")

    if result.change_set is not None:
        cs = result.change_set
        if cs.has_changes:
            cats = ", ".join(cs.change_categories)
            print(f"\n  Changes detected: {cats}")
            for c in cs.data_changes[:10]:
                print(f"    data: {c.path} ({c.change_type})")
            for c in cs.template_changes[:5]:
                print(f"    template: {c.path} ({c.change_type})")
            for c in cs.asset_changes[:5]:
                print(f"    asset: {c.path} ({c.change_type})")
        else:
            print("\n  No input changes detected")

    if result.drift_result is not None:
        dr = result.drift_result
        status = "PASS" if dr.passed else "DRIFT"
        print(f"\n  Drift: {status}")
        for f in dr.findings:
            marker = "✗" if f.severity == "error" else "⚠" if f.severity == "warning" else "○"
            print(f"    {marker} [{f.check_name}] {f.message}")
    elif args.baseline_dir:
        print("\n  Drift: no baseline found")

    if result.semantic_report is not None:
        sr = result.semantic_report
        if sr.issues:
            print(f"\n  Semantic: {len(sr.issues)} issue(s)")
            for si in sr.issues:
                marker = "✗" if si.severity == "error" else "⚠"
                print(f"    {marker} [{si.category}] {si.path}: {si.message}")
        else:
            print(f"\n  Semantic: clean ({len(sr.checks_run)} checks)")

    if args.save_baseline:
        print(f"\n  Baseline saved to {args.baseline_dir}")

    return 0


def _run_baseline(args: argparse.Namespace) -> int:
    """Manage render baselines."""
    import json as json_mod

    if args.baseline_action is None:
        print("error: specify 'save' or 'check'", file=sys.stderr)
        return 1

    template_path = Path(args.template)
    data_path = Path(args.data)

    if not data_path.exists():
        print(f"error: Data file not found: {data_path}", file=sys.stderr)
        return 1

    with open(data_path) as f:
        data = json_mod.load(f)

    if args.baseline_action == "save":
        try:
            result = audit(
                template_path,
                data,
                font_paths=args.font_paths,
                validate=args.validate,
                zugferd=args.zugferd,
                provenance=args.provenance,
                baseline_dir=args.baseline_dir,
                save_baseline=True,
            )
            print(f"Baseline saved: {template_path.name}")
            print(f"  PDF size: {len(result.pdf_bytes):,} bytes")
            print(f"  Fingerprint: {result.fingerprint.fingerprint[:40]}...")
            return 0
        except TrustRenderError as exc:
            print(_format_error(exc), file=sys.stderr)
            return 1

    if args.baseline_action == "check":
        try:
            result = audit(
                template_path,
                data,
                font_paths=args.font_paths,
                validate=args.validate,
                zugferd=args.zugferd,
                provenance=args.provenance,
                baseline_dir=args.baseline_dir,
            )
        except TrustRenderError as exc:
            print(_format_error(exc), file=sys.stderr)
            return 1

        if result.drift_result is None:
            print(f"No baseline found for {template_path.name}")
            print(f"  Run 'trustrender baseline save' first")
            return 1

        dr = result.drift_result
        status = "PASS" if dr.passed else "DRIFT DETECTED"
        print(f"Baseline check: {status}")
        for f in dr.findings:
            marker = "✗" if f.severity == "error" else "⚠" if f.severity == "warning" else "○"
            print(f"  {marker} [{f.check_name}] {f.message}")

        if dr.passed and not dr.findings:
            print("  All checks passed")

        return 0 if dr.passed else 1

    return 1


def _run_preflight(args: argparse.Namespace) -> int:
    import json

    from .readiness import preflight

    template_path = Path(args.template)
    data_path = Path(args.data)

    if not data_path.exists():
        print(f"error: Data file not found: {data_path}", file=sys.stderr)
        return 1

    with open(data_path) as f:
        data = json.load(f)

    semantic_hints = None
    if args.semantic:
        semantic_hints = _resolve_hints(template_path.name)
        if semantic_hints is None:
            print(
                f"warning: no semantic hints configured for '{template_path.name}'"
                " — skipping semantic checks",
                file=sys.stderr,
            )

    from . import _build_font_paths

    strict = getattr(args, "strict", False)
    resolved_fonts = _build_font_paths(getattr(args, "font_paths", None))
    verdict = preflight(
        template_path, data,
        font_paths=resolved_fonts,
        zugferd=args.zugferd,
        semantic_hints=semantic_hints,
        strict=strict,
    )

    # Header
    status = "PASS" if verdict.ready else "FAIL"
    warning_count = len(verdict.warnings)
    suffix = f" ({warning_count} warning{'s' if warning_count != 1 else ''})" if warning_count else ""
    print(f"Readiness: {status}{suffix}")
    print()

    # Stage results
    for stage in verdict.stages_checked:
        stage_errors = [i for i in verdict.errors if i.stage == stage]
        stage_warnings = [i for i in verdict.warnings if i.stage == stage]
        if stage_errors:
            marker = "✗ FAIL"
        elif stage_warnings:
            marker = "⚠ warn"
        else:
            marker = "✓ pass"
        print(f"  {stage:<14} {marker}")
        for issue in stage_errors:
            print(f"    {issue.path}: {issue.message}")
        for issue in stage_warnings:
            print(f"    {issue.path}: {issue.message}")

    # Profile eligibility
    if verdict.profile_eligible:
        print()
        eligible = "en16931" in verdict.profile_eligible
        print(f"  Profile eligibility: en16931 {'✓' if eligible else '✗'}")

    return 0 if verdict.ready else 1


def _format_error(exc: TrustRenderError) -> str:
    """Format a TrustRenderError for CLI output with full diagnostics."""
    lines = []
    lines.append(f"error[{exc.code.value}]: {str(exc).split(chr(10))[0]}")
    lines.append(f"  stage: {exc.stage}")
    if exc.template_path:
        lines.append(f"  template: {exc.template_path}")
    if exc.source_path:
        lines.append(f"  intermediate: {exc.source_path}")

    # Show full diagnostic if it's multi-line (more than the summary)
    summary = str(exc).split("\n")[0]
    if exc.detail and exc.detail != summary:
        lines.append("")
        for line in exc.detail.splitlines():
            lines.append(f"  {line}")

    return "\n".join(lines)


def _run_check(args: argparse.Namespace) -> int:
    """Inspect template contract or validate data against it."""
    import json

    from .contract import infer_contract_with_metadata, validate_data

    template_path = Path(args.template)
    if not template_path.exists():
        print(f"error: Template not found: {template_path}", file=sys.stderr)
        return 1
    if not template_path.name.endswith(".j2.typ"):
        print(f"error: Not a Jinja2 template: {template_path}", file=sys.stderr)
        return 1

    result = infer_contract_with_metadata(template_path)
    contract = result.contract

    if args.data:
        data_path = Path(args.data)
        if not data_path.exists():
            print(f"error: Data file not found: {data_path}", file=sys.stderr)
            return 1
        with open(data_path) as f:
            data = json.load(f)

        errors = validate_data(contract, data)
        if not errors:
            print(f"Valid: {args.data} matches {args.template}")
            if result.is_partial:
                print(f"  warning: contract is partial (unresolved includes: {', '.join(result.unresolved_includes)})")
            return 0
        print(
            f"error[DATA_CONTRACT]: {len(errors)} validation error(s)",
            file=sys.stderr,
        )
        print(f"  template: {args.template}", file=sys.stderr)
        print(f"  data: {args.data}", file=sys.stderr)
        print(file=sys.stderr)
        for e in errors:
            print(f"  {e.path}: {e.message}", file=sys.stderr)
        return 1

    # No --data: show inferred contract summary
    required_fields = [f for f in contract.values() if f.required]
    print(f"Template: {args.template}")
    print(f"Fields: {len(contract)} top-level ({len(required_fields)} required)")
    if result.is_partial:
        print(f"Partial: unresolved includes: {', '.join(result.unresolved_includes)}")
    print()
    for name, spec in sorted(contract.items()):
        marker = "*" if spec.required else " "
        desc = spec.expected_type
        if spec.expected_type == "object" and spec.children:
            child_names = ", ".join(sorted(spec.children.keys()))
            desc = f"object {{{child_names}}}"
        elif spec.expected_type in ("list[object]",) and spec.children:
            child_names = ", ".join(sorted(spec.children.keys()))
            desc = f"list[{{{child_names}}}]"
        print(f"  {marker} {name}: {desc}")
    return 0


def _run_render(args: argparse.Namespace) -> int:
    try:
        data = args.data
        if data == "-":
            data = sys.stdin.read()
        pdf_bytes = render(
            args.template,
            data,
            output=args.output,
            debug=args.debug,
            font_paths=args.font_paths,
            validate=args.validate,
            zugferd=args.zugferd,
            provenance=args.provenance,
        )
        print(f"Rendered {len(pdf_bytes):,} bytes -> {args.output}")
        if args.debug:
            print("  Debug mode: intermediate .typ file preserved in template directory")
        return 0
    except TrustRenderError as exc:
        print(_format_error(exc), file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _run_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .server import DEFAULT_MAX_BODY_SIZE, create_app

    if not args.templates:
        print(
            "error: --templates is required (or set TRUSTRENDER_TEMPLATES_DIR env var)",
            file=sys.stderr,
        )
        return 1

    # Resolve max body size: CLI arg > env var > default
    max_body_size = args.max_body_size
    if max_body_size is None:
        env_val = os.environ.get("TRUSTRENDER_MAX_BODY_SIZE")
        if env_val is not None:
            try:
                max_body_size = int(env_val)
            except ValueError:
                print(f"error: TRUSTRENDER_MAX_BODY_SIZE must be an integer, got: {env_val}", file=sys.stderr)
                return 1
    if max_body_size is None:
        max_body_size = DEFAULT_MAX_BODY_SIZE

    # Resolve CORS origins: --cors-origin flags + TRUSTRENDER_CORS_ORIGINS env var
    cors_origins = list(args.cors_origins)
    env_cors = os.environ.get("TRUSTRENDER_CORS_ORIGINS", "")
    if env_cors:
        cors_origins.extend(o.strip() for o in env_cors.split(",") if o.strip())
    cors_origins = list(dict.fromkeys(cors_origins))  # dedupe, preserve order

    app = create_app(
        args.templates,
        debug=args.debug,
        font_paths=args.font_paths,
        render_timeout=args.render_timeout,
        max_concurrent_renders=args.max_concurrent,
        max_body_size=max_body_size,
        dashboard=args.dashboard,
        history_path=args.history,
        cors_origins=cors_origins or None,
    )
    # Configure structured logging for trustrender modules.
    import logging

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )

    print(f"TrustRender server starting on {args.host}:{args.port}")
    print(f"  Templates: {args.templates}")
    print(f"  Debug: {args.debug}")
    print(f"  Render timeout: {args.render_timeout}s")
    print(f"  Max concurrent: {args.max_concurrent}")
    print(f"  Max body size: {max_body_size:,} bytes")
    if args.dashboard:
        print(f"  Dashboard: http://{args.host}:{args.port}/dashboard")
    if args.history:
        print(f"  History: {args.history}")
    if cors_origins:
        print(f"  CORS origins: {', '.join(cors_origins)}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
