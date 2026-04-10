"""Jinja2 preprocessing for Typst templates.

Escape contract
---------------
``typst_escape`` provides **text-interpolation-safe escaping** — it makes
user data safe for insertion into Typst content/text contexts.  It is NOT
universal Typst escaping.  It does not cover code mode, math mode, or other
context-sensitive syntax.

Escaped characters:
    \\  →  \\\\       (escape character itself)
    $   →  \\$        (math mode delimiter)
    #   →  \\#        (code prefix)
    @   →  \\@        (reference/citation)
    <   →  \\u{003c}  (label start — no backslash escape available)
    `   →  \\u{0060}  (raw text delimiter — no backslash escape available)
    ~   →  \\~        (non-breaking space)

Intentionally NOT escaped:
    _   Only triggers emphasis at word boundaries; escaping everywhere
        would make normal text ugly (e.g. ``snake_case``).
    *   Same reasoning as ``_``.
"""

from __future__ import annotations

import os
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError, UndefinedError
from markupsafe import Markup

from .errors import ErrorCode, FormforgeError


def typst_escape(value: object) -> object:
    """Escape Typst markup characters in a string value.

    This is applied automatically via Jinja2's ``finalize`` to every
    interpolated value.  Values wrapped with :func:`Markup` (e.g. via the
    ``typst_markup`` filter) bypass this function.
    """
    if isinstance(value, Markup):
        return value
    if not isinstance(value, str):
        return value
    s = value
    s = s.replace("\\", "\\\\")
    s = s.replace("$", "\\$")
    s = s.replace("#", "\\#")
    s = s.replace("@", "\\@")
    s = s.replace("<", "\\u{003c}")
    s = s.replace("`", "\\u{0060}")
    s = s.replace("~", "\\~")
    return s


def render_template(template_path: str | os.PathLike, data: dict) -> str:
    """Render a Jinja2 template with data, returning Typst markup.

    Auto-escapes Typst special characters in all string values.
    Values passed through the ``typst_markup`` filter bypass escaping.

    Raises:
        FormforgeError: With appropriate code for syntax or variable errors.
    """
    template_path = Path(template_path)

    from .filters import FILTERS

    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        finalize=typst_escape,
        keep_trailing_newline=True,
    )
    env.filters.update(FILTERS)

    try:
        template = env.get_template(template_path.name)
    except TemplateSyntaxError as exc:
        raise FormforgeError(
            f"Template syntax error: {exc.message}",
            code=ErrorCode.TEMPLATE_SYNTAX,
            stage="template_preprocess",
            detail=f"{exc.filename}:{exc.lineno}: {exc.message}",
            template_path=str(template_path),
        ) from exc

    try:
        return template.render(**data)
    except UndefinedError as exc:
        raise FormforgeError(
            f"Undefined template variable: {exc.message}",
            code=ErrorCode.TEMPLATE_VARIABLE,
            stage="template_preprocess",
            detail=str(exc),
            template_path=str(template_path),
        ) from exc
    except TemplateSyntaxError as exc:
        raise FormforgeError(
            f"Template syntax error: {exc.message}",
            code=ErrorCode.TEMPLATE_SYNTAX,
            stage="template_preprocess",
            detail=f"{exc.filename}:{exc.lineno}: {exc.message}",
            template_path=str(template_path),
        ) from exc
