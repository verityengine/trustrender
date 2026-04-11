"""Jinja2 preprocessing for Typst templates.

Escape contract
---------------
``typst_escape`` provides **text-interpolation-safe escaping** — it makes
user data safe for insertion into Typst content/text contexts.  It is NOT
universal Typst escaping.  It does not cover code mode, math mode, or other
context-sensitive syntax.

This matters because every template interpolates user data inside Typst
content blocks (``[...]``).  Unescaped ``]`` breaks out of the block, and
unescaped ``{`` enters code mode — both bypass the surrounding template
structure.

Escaped characters:
    \\  →  \\\\       (escape character itself)
    $   →  \\$        (math mode delimiter)
    #   →  \\#        (code prefix)
    @   →  \\@        (reference/citation)
    {   →  \\u{007b}  (code block start — no backslash escape available)
    }   →  \\u{007d}  (code block end — no backslash escape available)
    <   →  \\u{003c}  (label start — no backslash escape available)
    `   →  \\u{0060}  (raw text delimiter — no backslash escape available)
    ~   →  \\~        (non-breaking space)
    [   →  \\u{005b}  (content block start — no backslash escape available)
    ]   →  \\u{005d}  (content block end — no backslash escape available)

Line-start only (escaped via Unicode to prevent block-markup activation):
    =   →  \\u{003d}  (heading — only at start of line)
    -   →  \\u{002d}  (list item / horizontal rule — only at start of line)
    +   →  \\u{002b}  (numbered list item — only at start of line)
    /   →  \\u{002f}  (description list — only at start of line)

Intentionally NOT escaped:
    _   Only triggers emphasis at word boundaries; escaping everywhere
        would make normal text ugly (e.g. ``snake_case``).
    *   Same reasoning as ``_``.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError, UndefinedError
from markupsafe import Markup

from .errors import ErrorCode, TrustRenderError

# Single-pass translation table for bracket/brace characters.
# These MUST be replaced in one pass (via str.translate) because their
# Unicode escape sequences contain each other: \u{007b} contains "}" and
# \u{007d} contains "{".  Chained .replace() calls would corrupt output.
# str.translate acts only on the original string's literal characters and
# does NOT recursively reprocess inserted replacement sequences.
_BRACKET_TABLE = str.maketrans(
    {
        "{": "\\u{007b}",
        "}": "\\u{007d}",
        "[": "\\u{005b}",
        "]": "\\u{005d}",
    }
)

# Characters that trigger Typst block markup ONLY at line start.
# Escaped via Unicode so inline usage (dates, paths, equations) is untouched.
_LINE_START_CHARS = re.compile(r"^([=\-+/])", re.MULTILINE)
_LINE_START_ESCAPE = {
    "=": "\\u{003d}",
    "-": "\\u{002d}",
    "+": "\\u{002b}",
    "/": "\\u{002f}",
}


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
    s = s.translate(_BRACKET_TABLE)  # {, }, [, ] — must precede < and ` escapes
    s = s.replace("<", "\\u{003c}")
    s = s.replace("`", "\\u{0060}")
    s = s.replace("~", "\\~")
    s = _LINE_START_CHARS.sub(lambda m: _LINE_START_ESCAPE[m.group(1)], s)
    return s


def render_template(template_path: str | os.PathLike, data: dict) -> str:
    """Render a Jinja2 template with data, returning Typst markup.

    Auto-escapes Typst special characters in all string values.
    Values passed through the ``typst_markup`` filter bypass escaping.

    Raises:
        TrustRenderError: With appropriate code for syntax or variable errors.
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
        raise TrustRenderError(
            f"Template syntax error: {exc.message}",
            code=ErrorCode.TEMPLATE_SYNTAX,
            stage="template_preprocess",
            detail=f"{exc.filename}:{exc.lineno}: {exc.message}",
            template_path=str(template_path),
        ) from exc

    try:
        return template.render(**data)
    except UndefinedError as exc:
        raise TrustRenderError(
            f"Undefined template variable: {exc.message}",
            code=ErrorCode.TEMPLATE_VARIABLE,
            stage="template_preprocess",
            detail=str(exc),
            template_path=str(template_path),
        ) from exc
    except TemplateSyntaxError as exc:
        raise TrustRenderError(
            f"Template syntax error: {exc.message}",
            code=ErrorCode.TEMPLATE_SYNTAX,
            stage="template_preprocess",
            detail=f"{exc.filename}:{exc.lineno}: {exc.message}",
            template_path=str(template_path),
        ) from exc
