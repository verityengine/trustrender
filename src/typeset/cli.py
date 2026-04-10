"""CLI entry point for Typeset."""

from __future__ import annotations

import argparse
import sys

from . import TypesetError, __version__, render


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="typeset",
        description="Generate PDFs from structured data. No browser required.",
    )
    parser.add_argument("--version", action="version", version=f"typeset {__version__}")

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

    serve_cmd = sub.add_parser("serve", help="Start HTTP render server")
    serve_cmd.add_argument(
        "--templates", required=True, help="Template directory root"
    )
    serve_cmd.add_argument(
        "--port", type=int, default=8190, help="Port to listen on (default: 8190)"
    )
    serve_cmd.add_argument(
        "--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)"
    )
    serve_cmd.add_argument(
        "--debug", action="store_true", help="Enable debug mode"
    )
    serve_cmd.add_argument(
        "--font-path",
        action="append",
        dest="font_paths",
        help="Additional font directory (can be repeated)",
    )

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 1

    if args.command == "render":
        return _run_render(args)

    if args.command == "serve":
        return _run_serve(args)

    return 1


def _run_render(args: argparse.Namespace) -> int:
    try:
        pdf_bytes = render(
            args.template, args.data,
            output=args.output, debug=args.debug,
            font_paths=args.font_paths,
        )
        print(f"Rendered {len(pdf_bytes):,} bytes -> {args.output}")
        if args.debug:
            print("  Debug mode: intermediate .typ file preserved in template directory")
        return 0
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except TypesetError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


def _run_serve(args: argparse.Namespace) -> int:
    import uvicorn

    from .server import create_app

    app = create_app(args.templates, debug=args.debug, font_paths=args.font_paths)
    print(f"Typeset server starting on {args.host}:{args.port}")
    print(f"  Templates: {args.templates}")
    print(f"  Debug: {args.debug}")
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
    return 0


if __name__ == "__main__":
    sys.exit(main())
