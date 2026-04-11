"""Formforge: fast, code-first PDF generation from structured data."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .engine import compile_typst, compile_typst_file
from .errors import ErrorCode, FormforgeError

# Re-export for public API
from .errors import ErrorCode as ErrorCode  # noqa: F811
from .templates import render_template

__version__ = "0.1.0"

__all__ = ["render", "FormforgeError", "ErrorCode", "__version__", "bundled_font_dir"]


# Resolved once at import time — deterministic across local, test, and container.
# Check multiple locations: dev layout (src/formforge -> fonts/) and env var.
def _find_bundled_fonts() -> Path | None:
    """Find bundled font directory. Checked once at import time."""
    # 1. Environment variable (explicit override, used in containers)
    env_path = os.environ.get("FORMFORGE_FONT_PATH")
    if env_path:
        p = Path(env_path)
        if p.is_dir():
            return p.resolve()

    # 2. Development layout: src/formforge/__init__.py -> ../../fonts/
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
    validate: bool = False,
    zugferd: str | None = None,
    provenance: bool = False,
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
        validate: If True, validate data against the template's inferred
            structural contract before rendering.  Raises ``FormforgeError``
            with code ``DATA_CONTRACT`` if validation fails.
        zugferd: If set to ``"en16931"``, generate a ZUGFeRD-compliant
            PDF/A-3b with embedded CII XML.  Validates invoice data against
            EN 16931 requirements before generation.
        provenance: If True, embed a cryptographic generation proof in the
            PDF metadata.  Records template hash, data hash, engine version,
            and timestamp.  Use ``verify_provenance()`` to verify later.

    Returns:
        PDF file contents as bytes.

    Raises:
        FormforgeError: If rendering fails. Check ``code`` for the error category,
            ``stage`` for where it failed, and ``detail`` for the full diagnostic.
        FileNotFoundError: If the template or data file does not exist.
    """
    _SUPPORTED_ZUGFERD = {"en16931", "xrechnung"}
    if zugferd is not None and zugferd not in _SUPPORTED_ZUGFERD:
        raise FormforgeError(
            f"Unsupported zugferd profile: '{zugferd}'. Supported: {sorted(_SUPPORTED_ZUGFERD)}",
            code=ErrorCode.INVALID_DATA,
            stage="data_resolution",
        )

    template_path = Path(template)
    if not template_path.exists():
        raise FormforgeError(
            f"Template not found: {template_path}",
            code=ErrorCode.TEMPLATE_NOT_FOUND,
            stage="data_resolution",
            template_path=str(template_path),
        )

    data_dict = _resolve_data(data)
    is_jinja = template_path.name.endswith(".j2.typ")
    resolved_fonts = _build_font_paths(font_paths)

    # ZUGFeRD invoice data validation (EN 16931 requirements)
    if zugferd:
        from .zugferd import validate_zugferd_invoice_data

        errors = validate_zugferd_invoice_data(data_dict, profile=zugferd)
        if errors:
            detail = "\n".join(f"  {e.path}: {e.message}" for e in errors)
            raise FormforgeError(
                f"Invoice data does not satisfy EN 16931: {len(errors)} error(s)",
                code=ErrorCode.ZUGFERD_ERROR,
                stage="zugferd_validation",
                detail=detail,
                template_path=str(template_path),
                validation_errors=errors,
            )

    if is_jinja:
        # Pre-render contract validation (opt-in).
        if validate:
            from .contract import (
                format_contract_detail,
                format_contract_errors,
                infer_contract,
                validate_data,
            )

            contract = infer_contract(template_path)
            validation_errors = validate_data(contract, data_dict)
            if validation_errors:
                raise FormforgeError(
                    format_contract_errors(validation_errors, template_path.name),
                    code=ErrorCode.DATA_CONTRACT,
                    stage="data_validation",
                    template_path=str(template_path),
                    detail=format_contract_detail(validation_errors, contract),
                )

        rendered = render_template(template_path, data_dict)
        # Force PDF/A-3b when ZUGFeRD is requested
        pdf_standards = ["a-3b"] if zugferd else None
        pdf_bytes = compile_typst(
            rendered,
            template_path.parent,
            debug=debug,
            font_paths=resolved_fonts,
            template_path=template_path,
            pdf_standards=pdf_standards,
        )
    else:
        pdf_standards = ["a-3b"] if zugferd else None
        pdf_bytes = compile_typst_file(
            template_path,
            font_paths=resolved_fonts,
            pdf_standards=pdf_standards,
        )

    # ZUGFeRD post-processing: generate XML, embed into PDF
    if zugferd:
        from .zugferd import apply_zugferd, build_invoice_xml

        try:
            xml_bytes = build_invoice_xml(data_dict, profile=zugferd)
            pdf_bytes = apply_zugferd(pdf_bytes, xml_bytes)
        except FormforgeError:
            raise
        except Exception as exc:
            raise FormforgeError(
                f"ZUGFeRD generation failed: {exc}",
                code=ErrorCode.ZUGFERD_ERROR,
                stage="zugferd",
                detail=str(exc),
                template_path=str(template_path),
            ) from exc

    # Generation proof: embed cryptographic provenance in PDF metadata
    if provenance:
        from .provenance import create_provenance, embed_provenance

        record = create_provenance(template_path, data_dict)
        pdf_bytes = embed_provenance(pdf_bytes, record)

    if output is not None:
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(pdf_bytes)

    return pdf_bytes


def _resolve_data(data: dict | str | os.PathLike) -> dict:
    """Resolve data argument to a dict."""
    if isinstance(data, dict):
        return data

    if not isinstance(data, (str, os.PathLike)):
        raise FormforgeError(
            f"Data must be a dict, JSON string, or path to a .json file, "
            f"got {type(data).__name__}",
            code=ErrorCode.INVALID_DATA,
            stage="data_resolution",
        )

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
            raise FormforgeError(
                f"Data JSON must be an object, got {type(result).__name__}",
                code=ErrorCode.INVALID_DATA,
                stage="data_resolution",
            )
        except json.JSONDecodeError as exc:
            raise FormforgeError(
                f"Invalid data: not a valid file path or JSON string: {exc}",
                code=ErrorCode.INVALID_DATA,
                stage="data_resolution",
            ) from exc

    raise FormforgeError(
        f"Data must be a dict, JSON string, or path to a .json file, got {type(data).__name__}",
        code=ErrorCode.INVALID_DATA,
        stage="data_resolution",
    )
