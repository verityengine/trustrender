"""Typst compilation wrapper."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import typst as _typst

from .errors import TypesetError


def compile_typst(
    source: str,
    template_dir: str | os.PathLike,
    *,
    debug: bool = False,
    font_paths: list[str | os.PathLike] | None = None,
) -> bytes:
    """Compile rendered Typst markup to PDF bytes.

    Writes the source to a temp file in template_dir so that relative paths
    (images, assets) resolve correctly against the template's location.

    On success, the temp file is cleaned up (unless debug=True).
    On error, the temp file is always preserved for inspection.

    Args:
        font_paths: Additional font directories to search.  Passed directly
            to ``typst.compile(font_paths=...)``.

    Returns PDF bytes.
    """
    template_dir = Path(template_dir)

    compile_kwargs: dict = {"format": "pdf"}
    if font_paths:
        compile_kwargs["font_paths"] = [str(p) for p in font_paths]

    # Write source to a temp file next to the template
    fd, tmp_path = tempfile.mkstemp(suffix=".typ", dir=template_dir, prefix="_typeset_")
    try:
        with os.fdopen(fd, "w") as f:
            f.write(source)

        try:
            pdf_bytes = _typst.compile(tmp_path, **compile_kwargs)
        except _typst.TypstError as exc:
            # Preserve the intermediate file for debugging
            raise TypesetError(str(exc), source_path=tmp_path) from exc

        # Success — clean up unless debug mode
        if not debug:
            os.unlink(tmp_path)
        return pdf_bytes

    except TypesetError:
        raise
    except Exception:
        # Clean up on unexpected errors
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
