"""Formforge: fast, code-first PDF generation from structured data."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .engine import CompileBackend, compile_typst, compile_typst_file
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


def _render_document_pipeline(
    template_path: Path,
    data: dict,
    *,
    debug: bool = False,
    font_paths: list[str] | None = None,
    validate: bool = False,
    zugferd: str | None = None,
    provenance: bool = False,
    backend: CompileBackend | None = None,
    timeout: float | None = None,
) -> bytes:
    """Shared render pipeline: validate, preprocess, compile, post-process.

    All inputs must be pre-resolved (paths exist, data is a dict, fonts are
    string paths).  This is the single source of truth for render semantics —
    both ``render()`` and the server call this.

    Pipeline stages (in order):
      1. ZUGFeRD data validation (EN 16931 requirements)
      2. Contract validation (opt-in, Jinja2 templates only)
      3. Template preprocessing (Jinja2) + Typst compilation
      4. ZUGFeRD post-processing (XML build + PDF embed)
      5. Provenance embedding (after all other processing)

    The ordering of stages 4 and 5 is load-bearing: provenance uses
    clone_from to preserve ZUGFeRD metadata and embedded files.

    If ``FORMFORGE_HISTORY`` is set, a stage-by-stage RenderTrace is
    recorded to the trace store after each render (success or failure).
    """
    import hashlib
    import time

    from .trace import RenderTrace, StageTrace, get_store

    is_jinja = template_path.name.endswith(".j2.typ")
    trace = RenderTrace(
        template_name=template_path.name,
        template_hash=f"sha256:{hashlib.sha256(template_path.read_bytes()).hexdigest()[:16]}",
        data_hash=f"sha256:{hashlib.sha256(json.dumps(data, sort_keys=True, separators=(',',':')).encode()).hexdigest()[:16]}",
        engine_version=__version__,
        zugferd_profile=zugferd or "",
        validated=validate,
    )
    pipeline_start = time.monotonic()

    def _record_trace(outcome: str, pdf_size: int = 0, error: FormforgeError | None = None) -> None:
        trace.outcome = outcome
        trace.pdf_size = pdf_size
        trace.total_ms = int((time.monotonic() - pipeline_start) * 1000)
        if error:
            trace.error_code = error.code.value
            trace.error_stage = error.stage
            trace.error_message = str(error).split("\n")[0]
        store = get_store()
        if store:
            try:
                store.record(trace)
            except Exception:
                pass  # Lineage is observability, not a gate

    try:
        # 1. ZUGFeRD invoice data validation
        if zugferd:
            from .zugferd import validate_zugferd_invoice_data

            t0 = time.monotonic()
            errors = validate_zugferd_invoice_data(data, profile=zugferd)
            stage = StageTrace(
                stage="zugferd_validation",
                status="fail" if errors else "pass",
                duration_ms=int((time.monotonic() - t0) * 1000),
                checks_run=len(errors) + (1 if not errors else 0),
                checks_passed=0 if errors else 1,
                checks_failed=len(errors),
                errors=[{"path": e.path, "message": e.message} for e in errors],
                metadata={"profile": zugferd},
            )
            trace.stages.append(stage)
            if errors:
                detail = "\n".join(f"  {e.path}: {e.message}" for e in errors)
                exc = FormforgeError(
                    f"Invoice data does not satisfy EN 16931: {len(errors)} error(s)",
                    code=ErrorCode.ZUGFERD_ERROR,
                    stage="zugferd_validation",
                    detail=detail,
                    template_path=str(template_path),
                    validation_errors=errors,
                )
                _record_trace("error", error=exc)
                raise exc

        # 2. Contract validation (opt-in, Jinja2 templates only)
        if validate and is_jinja:
            from .contract import (
                format_contract_detail,
                format_contract_errors,
                infer_contract,
                validate_data,
            )

            t0 = time.monotonic()
            contract = infer_contract(template_path)
            validation_errors = validate_data(contract, data)
            stage = StageTrace(
                stage="contract_validation",
                status="fail" if validation_errors else "pass",
                duration_ms=int((time.monotonic() - t0) * 1000),
                checks_run=len(contract),
                checks_passed=len(contract) - len(validation_errors),
                checks_failed=len(validation_errors),
                errors=[{"path": e.path, "message": e.message} for e in validation_errors],
            )
            trace.stages.append(stage)
            if validation_errors:
                exc = FormforgeError(
                    format_contract_errors(validation_errors, template_path.name),
                    code=ErrorCode.DATA_CONTRACT,
                    stage="data_validation",
                    template_path=str(template_path),
                    detail=format_contract_detail(validation_errors, contract),
                )
                _record_trace("error", error=exc)
                raise exc

        # 3. Template preprocessing + compilation
        t0 = time.monotonic()
        pdf_standards = ["a-3b"] if zugferd else None
        if is_jinja:
            rendered = render_template(template_path, data)
            pdf_bytes = compile_typst(
                rendered,
                template_path.parent,
                debug=debug,
                font_paths=font_paths,
                template_path=template_path,
                backend=backend,
                timeout=timeout,
                pdf_standards=pdf_standards,
            )
        else:
            pdf_bytes = compile_typst_file(
                template_path,
                font_paths=font_paths,
                backend=backend,
                timeout=timeout,
                pdf_standards=pdf_standards,
            )
        trace.stages.append(StageTrace(
            stage="compilation",
            status="pass",
            duration_ms=int((time.monotonic() - t0) * 1000),
            metadata={
                "template_type": "jinja2" if is_jinja else "raw",
                "pdf_standards": pdf_standards or [],
                "pdf_size": len(pdf_bytes),
            },
        ))

        # 4. ZUGFeRD post-processing
        if zugferd:
            from .zugferd import apply_zugferd, build_invoice_xml

            t0 = time.monotonic()
            try:
                xml_bytes = build_invoice_xml(data, profile=zugferd)
                pdf_bytes = apply_zugferd(pdf_bytes, xml_bytes)
                trace.stages.append(StageTrace(
                    stage="zugferd_postprocess",
                    status="pass",
                    duration_ms=int((time.monotonic() - t0) * 1000),
                    metadata={"xml_size": len(xml_bytes), "profile": zugferd},
                ))
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

        # 5. Provenance (AFTER ZUGFeRD — uses clone_from to preserve metadata)
        if provenance:
            from .provenance import create_provenance, embed_provenance

            t0 = time.monotonic()
            prov_record = create_provenance(template_path, data)
            pdf_bytes = embed_provenance(pdf_bytes, prov_record)
            trace.stages.append(StageTrace(
                stage="provenance",
                status="pass",
                duration_ms=int((time.monotonic() - t0) * 1000),
                metadata={"proof_hash": prov_record.proof[:30]},
            ))
            trace.provenance_hash = prov_record.proof

        _record_trace("success", pdf_size=len(pdf_bytes))
        return pdf_bytes

    except FormforgeError as exc:
        if not trace.outcome:  # Not already recorded by a stage
            _record_trace("error", error=exc)
        raise


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
    resolved_fonts = _build_font_paths(font_paths)

    pdf_bytes = _render_document_pipeline(
        template_path,
        data_dict,
        debug=debug,
        font_paths=resolved_fonts,
        validate=validate,
        zugferd=zugferd,
        provenance=provenance,
    )

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
