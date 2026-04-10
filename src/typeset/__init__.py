"""Typeset: fast, code-first PDF generation from structured data."""

from __future__ import annotations

import json
import os
from pathlib import Path

import typst as _typst

from .engine import compile_typst
from .errors import TypesetError
from .templates import render_template

__version__ = "0.1.0"

__all__ = ["render", "TypesetError", "__version__", "bundled_font_dir"]

# Resolved once at import time — deterministic across local, test, and container.
# Check multiple locations: dev layout (src/typeset -> fonts/) and env var.
def _find_bundled_fonts() -> Path | None:
    """Find bundled font directory. Checked once at import time."""
    # 1. Environment variable (explicit override, used in containers)
    env_path = os.environ.get("TYPESET_FONT_PATH")
    if env_path:
        p = Path(env_path)
        if p.is_dir():
            return p.resolve()

    # 2. Development layout: src/typeset/__init__.py -> ../../fonts/
    dev_path = Path(__file__).resolve().parent.parent.parent / "fonts"
    if dev_path.is_dir():
        return dev_path

    return None


_BUNDLED_FONT_DIR = _find_bundled_fonts()


def bundled_font_dir() -> Path | None:
    """Return the path to the bundled font directory, or None if not found."""
    return _BUNDLED_FONT_DIR


def _build_font_paths(
    font_paths: list[str | os.PathLike] | None,
) -> list[str] | None:
    """Build the final font_paths list.

    Font precedence:
      1. Explicit font_paths passed by caller
      2. Bundled font directory (``fonts/`` in the package)
      3. System fonts (Typst default behavior — always included)

    Caller paths extend the bundled defaults.
    """
    result: list[str] = []
    if font_paths:
        result.extend(str(p) for p in font_paths)
    bundled = bundled_font_dir()
    if bundled:
        bundled_str = str(bundled)
        if bundled_str not in result:
            result.append(bundled_str)
    return result or None


def render(
    template: str | os.PathLike,
    data: dict | str | os.PathLike,
    *,
    output: str | os.PathLike | None = None,
    debug: bool = False,
    font_paths: list[str | os.PathLike] | None = None,
) -> bytes:
    """Render a PDF from a template and data.

    Args:
        template: Path to a template file.
            - ``.j2.typ``: Jinja2 template preprocessed then compiled with Typst.
            - ``.typ``: Raw Typst file compiled directly.
        data: Template data as a dict, a JSON string, or a path to a ``.json`` file.
        output: If provided, write the PDF to this path.
        debug: If True, preserve the intermediate ``.typ`` file after rendering.
            On error, the intermediate file is always preserved regardless of this flag.
        font_paths: Additional font directories.  These are prepended to the
            bundled font directory.

    Returns:
        PDF file contents as bytes.

    Raises:
        TypesetError: If rendering fails. The error includes the path to the
            intermediate ``.typ`` file for debugging.
        FileNotFoundError: If the template or data file does not exist.
    """
    template_path = Path(template)
    if not template_path.exists():
        raise FileNotFoundError(f"Template not found: {template_path}")

    data_dict = _resolve_data(data)
    is_jinja = template_path.name.endswith(".j2.typ")
    resolved_fonts = _build_font_paths(font_paths)

    if is_jinja:
        rendered = render_template(template_path, data_dict)
        pdf_bytes = compile_typst(
            rendered,
            template_path.parent,
            debug=debug,
            font_paths=resolved_fonts,
        )
    else:
        compile_kwargs: dict = {"format": "pdf"}
        if resolved_fonts:
            compile_kwargs["font_paths"] = resolved_fonts
        try:
            pdf_bytes = _typst.compile(str(template_path), **compile_kwargs)
        except _typst.TypstError as exc:
            raise TypesetError(str(exc)) from exc

    if output is not None:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(pdf_bytes)

    return pdf_bytes


def _resolve_data(data: dict | str | os.PathLike) -> dict:
    """Resolve data argument to a dict."""
    if isinstance(data, dict):
        return data

    # Try as file path first
    path = Path(data) if not isinstance(data, str) else None
    if path is None:
        # Could be a JSON string or a file path string
        candidate = Path(data)
        if candidate.exists() and candidate.suffix == ".json":
            path = candidate

    if path is not None and path.exists():
        with open(path) as f:
            return json.load(f)

    # Try as JSON string
    if isinstance(data, str):
        try:
            result = json.loads(data)
            if isinstance(result, dict):
                return result
            raise TypesetError(
                f"Data JSON must be an object, got {type(result).__name__}"
            )
        except json.JSONDecodeError as exc:
            msg = f"Invalid data: not a valid file path or JSON string: {exc}"
            raise TypesetError(msg) from exc

    raise TypesetError(
        f"Data must be a dict, JSON string, or path to a .json file, "
        f"got {type(data).__name__}"
    )
