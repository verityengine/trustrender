"""CLI entry point for Formforge."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import FormforgeError, __version__, render


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
        "--validate",
        action="store_true",
        help="Validate data against template contract before rendering",
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

    if args.command == "serve":
        return _run_serve(args)

    if args.command == "doctor":
        from .doctor import run_doctor

        return run_doctor(smoke=args.smoke)

    return 1


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

    from .contract import infer_contract, validate_data

    template_path = Path(args.template)
    if not template_path.exists():
        print(f"error: Template not found: {template_path}", file=sys.stderr)
        return 1
    if not template_path.name.endswith(".j2.typ"):
        print(f"error: Not a Jinja2 template: {template_path}", file=sys.stderr)
        return 1

    contract = infer_contract(template_path)

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

    app = create_app(args.templates, debug=args.debug, font_paths=args.font_paths)
    print(f"Formforge server starting on {args.host}:{args.port}")
    print(f"  Templates: {args.templates}")
    print(f"  Debug: {args.debug}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
