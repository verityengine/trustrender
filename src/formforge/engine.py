"""Typst compilation backends and error classification.

Two backends share one compile contract:

  TypstPyBackend  — in-process via typst-py (Python binding)
  TypstCliBackend — subprocess via ``typst compile`` CLI

Backend selection:
  1. ``force`` parameter on ``get_backend()``
  2. ``FORMFORGE_BACKEND`` env var (``typst-py`` or ``typst-cli``)
  3. Auto-detect: try typst-py import, fall back to CLI
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path
from typing import Protocol, runtime_checkable

from .errors import ErrorCode, FormforgeError


def _classify_typst_error(message: str) -> ErrorCode:
    """Classify a Typst error message into an error code.

    Inspects the raw diagnostic string from Typst to determine the failure
    category.  Works on output from both the Python binding and the CLI —
    they share the same error formatting pipeline.

    This is necessarily heuristic — Typst exposes errors as formatted strings,
    not structured data.

    Known limitations:
      - Classification is based on substring matching in English error messages.
      - Some failures will only match COMPILE_ERROR (the catch-all).
      - If Typst changes its error wording, classification may degrade to
        COMPILE_ERROR, which is safe but less specific.
      - MISSING_FONT rarely fires in practice because Typst silently falls
        back to a default font for unknown families.  This classification
        only catches explicit font errors (e.g., corrupted font files).
        Silent fallback is inherently undetectable at the error level.
    """
    lower = message.lower()

    # Missing file / asset errors
    if "file not found" in lower or "not found" in lower and "image" in lower:
        return ErrorCode.MISSING_ASSET
    if "failed to load image" in lower:
        return ErrorCode.MISSING_ASSET

    # Font errors (rare — Typst usually falls back silently)
    if "unknown font family" in lower or "font" in lower and "not found" in lower:
        return ErrorCode.MISSING_FONT

    return ErrorCode.COMPILE_ERROR


# ---------------------------------------------------------------------------
# Backend protocol
# ---------------------------------------------------------------------------

@runtime_checkable
class CompileBackend(Protocol):
    """Contract for Typst compilation backends.

    Each implementation takes a path to a ``.typ`` file, compiles it, and
    returns PDF bytes.  Errors are raised as ``FormforgeError`` with a
    classified ``ErrorCode``.
    """

    def compile(
        self,
        input_path: str | os.PathLike,
        *,
        format: str = "pdf",
        font_paths: list[str] | None = None,
        timeout: float | None = None,
    ) -> bytes: ...


# ---------------------------------------------------------------------------
# Backends
# ---------------------------------------------------------------------------

class TypstPyBackend:
    """In-process compilation via typst-py (the Python binding).

    The ``timeout`` parameter is accepted for protocol compatibility but
    cannot be honored — in-process compilation is not killable.  Use
    ``TypstCliBackend`` when real timeout/cancellation is required.
    """

    def compile(
        self,
        input_path: str | os.PathLike,
        *,
        format: str = "pdf",
        font_paths: list[str] | None = None,
        timeout: float | None = None,
    ) -> bytes:
        import typst as _typst

        kwargs: dict = {"format": format}
        if font_paths:
            kwargs["font_paths"] = font_paths
        try:
            return _typst.compile(str(input_path), **kwargs)
        except _typst.TypstError as exc:
            raw = str(exc)
            code = _classify_typst_error(raw)
            raise FormforgeError(
                raw.split("\n")[0],
                code=code,
                stage="compilation",
                detail=raw,
                source_path=str(input_path),
            ) from exc


class TypstCliBackend:
    """Subprocess compilation via the ``typst`` CLI.

    Timeout note:
        The ``compile_timeout`` is a **backend execution safety net** — it
        prevents a runaway Typst process from living forever.  This is
        distinct from the server's request-layer timeout (``asyncio.wait_for``
        in ``server.py``), which controls how long a *client* waits for a
        response.  They are semantically different and intentionally separate.
    """

    def __init__(
        self,
        typst_bin: str = "typst",
        compile_timeout: float = 60,
    ):
        self._bin = typst_bin
        self._timeout = compile_timeout

    def compile(
        self,
        input_path: str | os.PathLike,
        *,
        format: str = "pdf",
        font_paths: list[str] | None = None,
        timeout: float | None = None,
    ) -> bytes:
        effective_timeout = timeout if timeout is not None else self._timeout
        cmd = [self._bin, "compile", str(input_path), "-", "--format", format]
        if font_paths:
            for fp in font_paths:
                cmd.extend(["--font-path", str(fp)])

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                timeout=effective_timeout,
            )
        except FileNotFoundError:
            raise FormforgeError(
                f"Typst CLI not found at '{self._bin}'. "
                f"Install Typst (https://typst.app) or set FORMFORGE_BACKEND=typst-py",
                code=ErrorCode.BACKEND_ERROR,
                stage="compilation",
            )
        except subprocess.TimeoutExpired as exc:
            raise FormforgeError(
                f"Typst compilation timed out after {effective_timeout}s",
                code=ErrorCode.RENDER_TIMEOUT,
                stage="compilation",
            ) from exc

        if result.returncode != 0:
            raw = result.stderr.decode("utf-8", errors="replace")
            code = _classify_typst_error(raw)
            raise FormforgeError(
                raw.split("\n")[0],
                code=code,
                stage="compilation",
                detail=raw,
                source_path=str(input_path),
            )

        return result.stdout


# ---------------------------------------------------------------------------
# Backend factory
# ---------------------------------------------------------------------------

def get_backend(*, force: str | None = None) -> CompileBackend:
    """Return a compilation backend instance.

    Selection precedence:
      1. ``force`` parameter (``"typst-py"`` or ``"typst-cli"``)
      2. ``FORMFORGE_BACKEND`` environment variable
      3. Auto-detect: try ``import typst``, fall back to CLI

    Backends are cheap to construct (no state, no connections), so a fresh
    instance is returned each call.  No global caching.
    """
    choice = force or os.environ.get("FORMFORGE_BACKEND")

    if choice == "typst-cli":
        return TypstCliBackend()
    if choice == "typst-py":
        return TypstPyBackend()
    if choice is not None:
        raise ValueError(
            f"Unknown backend: {choice!r}. Use 'typst-py' or 'typst-cli'."
        )

    # Auto-detect: prefer typst-py
    try:
        import typst  # noqa: F401
        return TypstPyBackend()
    except ImportError:
        return TypstCliBackend()


# ---------------------------------------------------------------------------
# Compile functions (used by __init__.py)
# ---------------------------------------------------------------------------

def compile_typst_file(
    path: str | os.PathLike,
    *,
    font_paths: list[str] | None = None,
    backend: CompileBackend | None = None,
    timeout: float | None = None,
) -> bytes:
    """Compile an existing ``.typ`` file to PDF bytes.

    For raw Typst files that don't need Jinja2 preprocessing.
    No temp file created — the file already exists on disk.

    Args:
        path: Path to the ``.typ`` file.
        font_paths: Additional font directories.
        backend: Explicit backend instance.  If None, uses ``get_backend()``.
        timeout: Compile timeout in seconds.  Passed to the backend.
            Only honored by ``TypstCliBackend`` (subprocess kill).
    """
    backend = backend or get_backend()
    try:
        return backend.compile(path, format="pdf", font_paths=font_paths, timeout=timeout)
    except FormforgeError as exc:
        if exc.template_path is None:
            exc.template_path = str(path)
        raise


def compile_typst(
    source: str,
    template_dir: str | os.PathLike,
    *,
    debug: bool = False,
    font_paths: list[str | os.PathLike] | None = None,
    template_path: str | os.PathLike | None = None,
    backend: CompileBackend | None = None,
    timeout: float | None = None,
) -> bytes:
    """Compile rendered Typst markup to PDF bytes.

    Writes the source to a temp file in template_dir so that relative paths
    (images, assets) resolve correctly against the template's location.

    On success, the temp file is cleaned up (unless debug=True).
    On compile error, the temp file is preserved for inspection.
    On timeout, the temp file is cleaned up (unless debug=True) to prevent
    accumulating orphan artifacts under repeated timeout failures.

    Args:
        source: Typst markup string to compile.
        template_dir: Directory containing the template and its assets.
        debug: If True, preserve intermediate .typ file after success.
        font_paths: Additional font directories to search.
        template_path: Original template path (for error attribution).
        backend: Explicit backend instance.  If None, uses ``get_backend()``.
        timeout: Compile timeout in seconds.  Passed to the backend.
            Only honored by ``TypstCliBackend`` (subprocess kill).

    Returns PDF bytes.
    """
    template_dir = Path(template_dir)
    backend = backend or get_backend()
    resolved_fonts = [str(p) for p in font_paths] if font_paths else None

    # Write source to a temp file next to the template
    fd, tmp_path = tempfile.mkstemp(suffix=".typ", dir=template_dir, prefix="_formforge_")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(source)

        try:
            pdf_bytes = backend.compile(
                tmp_path, format="pdf", font_paths=resolved_fonts, timeout=timeout,
            )
        except FormforgeError as exc:
            if exc.template_path is None and template_path:
                exc.template_path = str(template_path)
            # Timeout cleanup policy: don't accumulate orphan artifacts in
            # production.  Preserve only in debug mode (developer asked for it).
            # Other errors always preserve the temp file for inspection.
            if exc.code == ErrorCode.RENDER_TIMEOUT and not debug:
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                exc.source_path = None
            raise

        # Success — clean up unless debug mode
        if not debug:
            os.unlink(tmp_path)
        return pdf_bytes

    except FormforgeError:
        raise
    except Exception:
        # Clean up on unexpected errors
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
