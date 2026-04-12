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
    render_cmd.add_argument("data", help="Path to JSON data file")
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

    sub.add_parser("quickstart", help="Create and render a sample invoice PDF")

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        print()
        print("  Get started:  trustrender quickstart")
        print()
        return 1

    if args.command == "quickstart":
        return _run_quickstart()

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


def _run_quickstart() -> int:
    """Scaffold a sample invoice template + data and render a PDF."""
    import json

    outdir = Path("trustrender-quickstart")
    if outdir.exists():
        print(f"error: {outdir}/ already exists. Remove it or use a different directory.", file=sys.stderr)
        return 1

    template_content = r"""// Invoice layout
#set page(paper: "us-letter", margin: (top: 0.8in, bottom: 0.8in, x: 0.9in))
#set text(size: 10pt, font: "Inter")

#let accent = rgb("#C4622A")
#let muted = rgb("#7A7670")

#align(right, text(size: 24pt, weight: "bold", tracking: 0.5pt)[INVOICE])
#v(4pt)
#align(right, text(size: 9pt, fill: muted)[{{ invoice_number }} · {{ invoice_date }}])
#v(16pt)

#grid(columns: (1fr, 1fr),
  [ #text(size: 7pt, fill: muted)[FROM] \ #strong[{{ sender.name }}] \ {{ sender.address }} \ {{ sender.email }} ],
  [ #text(size: 7pt, fill: muted)[TO] \ #strong[{{ recipient.name }}] \ {{ recipient.address }} \ {{ recipient.email }} ],
)
#v(16pt)
#line(length: 100%, stroke: 0.5pt + muted)
#v(8pt)

#table(
  columns: (auto, 1fr, auto, auto, auto),
  stroke: none,
  inset: (x: 8pt, y: 6pt),
  fill: (_, row) => if row == 0 { rgb("#F5F4F2") },
  table.header[\#][Description][Qty][Price][Amount],
  {% for item in items %}
  [{{ item.num }}], [{{ item.description }}], [{{ item.qty }}], [{{ item.unit_price }}], [{{ item.amount }}],
  {% endfor %}
)
#v(8pt)
#line(length: 100%, stroke: 0.5pt + muted)
#v(8pt)

#align(right)[
  #text(size: 9pt, fill: muted)[Subtotal: {{ subtotal }}] \
  #text(size: 9pt, fill: muted)[Tax ({{ tax_rate }}): {{ tax_amount }}] \
  #v(4pt)
  #text(size: 14pt, weight: "bold", fill: accent)[Total: {{ total }}]
]

#v(24pt)
#text(size: 8pt, fill: muted)[
  Payment terms: {{ payment_terms }} \
  {{ notes }}
]
"""

    data_content = {
        "invoice_number": "INV-2026-0001",
        "invoice_date": "April 11, 2026",
        "payment_terms": "Net 30",
        "sender": {
            "name": "Acme Corp",
            "address": "123 Business Ave, San Francisco, CA 94105",
            "email": "billing@acme.com",
        },
        "recipient": {
            "name": "Contoso Ltd",
            "address": "456 Enterprise Blvd, New York, NY 10001",
            "email": "ap@contoso.com",
        },
        "items": [
            {"num": 1, "description": "Website redesign", "qty": 1, "unit_price": "$4,500.00", "amount": "$4,500.00"},
            {"num": 2, "description": "SEO audit and optimization", "qty": 1, "unit_price": "$1,200.00", "amount": "$1,200.00"},
            {"num": 3, "description": "Monthly hosting (3 months)", "qty": 3, "unit_price": "$150.00", "amount": "$450.00"},
        ],
        "subtotal": "$6,150.00",
        "tax_rate": "8.5%",
        "tax_amount": "$522.75",
        "total": "$6,672.75",
        "notes": "Thank you for your business.",
    }

    outdir.mkdir()
    template_path = outdir / "invoice.j2.typ"
    data_path = outdir / "invoice_data.json"
    output_path = outdir / "invoice.pdf"

    template_path.write_text(template_content)
    data_path.write_text(json.dumps(data_content, indent=2) + "\n")

    print()
    print(f"  Created:")
    print(f"    {template_path}")
    print(f"    {data_path}")
    print()
    print(f"  Starting server at http://localhost:8190")
    print(f"  Opening in your browser...")
    print()

    import threading
    import webbrowser

    threading.Timer(1.0, lambda: webbrowser.open("http://localhost:8190/#app")).start()

    import uvicorn
    from .server import create_app

    app = create_app(
        str(outdir),
        dashboard=True,
    )
    uvicorn.run(app, host="127.0.0.1", port=8190, log_level="warning")
    return 0


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
        pdf_bytes = render(
            args.template,
            args.data,
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
