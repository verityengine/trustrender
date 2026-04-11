"""CLI entry point for Formforge."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import AuditResult, FormforgeError, __version__, audit, render


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="formforge",
        description="Generate PDFs from structured data. No browser required.",
    )
    parser.add_argument("--version", action="version", version=f"formforge {__version__}")

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
    render_cmd.add_argument(
        "--font-path",
        action="append",
        dest="font_paths",
        help="Additional font directory (can be repeated)",
    )
    render_cmd.add_argument(
        "--no-validate",
        action="store_false",
        dest="validate",
        help="Skip data contract validation before rendering",
    )
    render_cmd.set_defaults(validate=True)
    render_cmd.add_argument(
        "--zugferd",
        choices=["en16931", "xrechnung"],
        help="Generate ZUGFeRD-compliant PDF (en16931 or xrechnung)",
    )
    render_cmd.add_argument(
        "--provenance",
        action="store_true",
        help="Embed cryptographic generation proof in PDF metadata",
    )

    check_cmd = sub.add_parser("check", help="Inspect or validate template data contract")
    check_cmd.add_argument("template", help="Path to .j2.typ template")
    check_cmd.add_argument("--data", help="Path to JSON data file to validate against")

    serve_cmd = sub.add_parser("serve", help="Start HTTP render server")
    serve_cmd.add_argument("--templates", required=True, help="Template directory root")
    serve_cmd.add_argument(
        "--port", type=int, default=8190, help="Port to listen on (default: 8190)"
    )
    serve_cmd.add_argument(
        "--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)"
    )
    serve_cmd.add_argument("--debug", action="store_true", help="Enable debug mode")
    serve_cmd.add_argument(
        "--font-path",
        action="append",
        dest="font_paths",
        help="Additional font directory (can be repeated)",
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

    preflight_cmd = sub.add_parser("preflight", help="Pre-render readiness verification")
    preflight_cmd.add_argument("template", help="Path to template (.j2.typ or .typ)")
    preflight_cmd.add_argument("data", help="Path to JSON data file")
    preflight_cmd.add_argument(
        "--zugferd",
        choices=["en16931", "xrechnung"],
        help="Check compliance eligibility for this profile",
    )
    preflight_cmd.add_argument(
        "--semantic",
        action="store_true",
        help="Run semantic validation (arithmetic, dates, completeness)",
    )

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
    audit_cmd.add_argument(
        "--no-validate",
        action="store_false",
        dest="validate",
        help="Skip data contract validation before rendering",
    )
    audit_cmd.set_defaults(validate=True)
    audit_cmd.add_argument(
        "--font-path",
        action="append",
        dest="font_paths",
        help="Additional font directory (can be repeated)",
    )
    audit_cmd.add_argument(
        "--zugferd",
        choices=["en16931", "xrechnung"],
        help="Generate ZUGFeRD-compliant PDF",
    )
    audit_cmd.add_argument(
        "--provenance",
        action="store_true",
        help="Embed cryptographic generation proof",
    )
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
    baseline_save.add_argument("--font-path", action="append", dest="font_paths")
    baseline_save.add_argument("--no-validate", action="store_false", dest="validate")
    baseline_save.set_defaults(validate=True)
    baseline_save.add_argument("--zugferd", choices=["en16931", "xrechnung"])
    baseline_save.add_argument("--provenance", action="store_true")

    baseline_check = baseline_sub.add_parser("check", help="Check against baseline")
    baseline_check.add_argument("template", help="Path to template")
    baseline_check.add_argument("data", help="Path to JSON data file")
    baseline_check.add_argument(
        "--baseline-dir",
        required=True,
        help="Baseline directory",
    )
    baseline_check.add_argument("--font-path", action="append", dest="font_paths")
    baseline_check.add_argument("--no-validate", action="store_false", dest="validate")
    baseline_check.set_defaults(validate=True)
    baseline_check.add_argument("--zugferd", choices=["en16931", "xrechnung"])
    baseline_check.add_argument("--provenance", action="store_true")

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

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

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


def _run_history(args: argparse.Namespace) -> int:
    from .trace import get_store

    store = get_store()
    if not store:
        print(
            "error: History not enabled. Set FORMFORGE_HISTORY=~/.formforge/history.db",
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
            "error: History not enabled. Set FORMFORGE_HISTORY=~/.formforge/history.db",
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
    """Auto-detect semantic hints based on template name.

    Returns None for unrecognized template types — no fake confidence.
    """
    from .semantic import INVOICE_HINTS, RECEIPT_HINTS, STATEMENT_HINTS

    name = template_name.lower()
    if "invoice" in name or "einvoice" in name:
        return INVOICE_HINTS
    if "receipt" in name:
        return RECEIPT_HINTS
    if "statement" in name:
        return STATEMENT_HINTS
    return None


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
    except FormforgeError as exc:
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
        except FormforgeError as exc:
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
        except FormforgeError as exc:
            print(_format_error(exc), file=sys.stderr)
            return 1

        if result.drift_result is None:
            print(f"No baseline found for {template_path.name}")
            print(f"  Run 'formforge baseline save' first")
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

    verdict = preflight(template_path, data, zugferd=args.zugferd, semantic_hints=semantic_hints)

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
        profiles = []
        for p in ("en16931", "xrechnung"):
            if p in verdict.profile_eligible:
                profiles.append(f"{p} ✓")
            else:
                profiles.append(f"{p} ✗")
        print(f"  Profile eligibility: {', '.join(profiles)}")

    return 0 if verdict.ready else 1


def _format_error(exc: FormforgeError) -> str:
    """Format a FormforgeError for CLI output with full diagnostics."""
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
    except FormforgeError as exc:
        print(_format_error(exc), file=sys.stderr)
        return 1
    except FileNotFoundError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _run_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .server import create_app

    app = create_app(
        args.templates,
        debug=args.debug,
        font_paths=args.font_paths,
        dashboard=args.dashboard,
        history_path=args.history,
    )
    print(f"Formforge server starting on {args.host}:{args.port}")
    print(f"  Templates: {args.templates}")
    print(f"  Debug: {args.debug}")
    if args.dashboard:
        print(f"  Dashboard: http://{args.host}:{args.port}/dashboard")
    if args.history:
        print(f"  History: {args.history}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
