"""Jinja2 filters for Typst template authoring.

These filters are registered automatically on the Jinja2 environment used
by :func:`typeset.templates.render_template`.
"""

from __future__ import annotations

from markupsafe import Markup

from .templates import typst_escape


def typst_money(value: str, negative_color: str = "#c0392b") -> Markup:
    """Format a currency string, wrapping negative values in colored text.

    Accepts a display-formatted currency string (e.g. ``"$1,200.00"`` or
    ``"-$500.00"``).  This is a display filter only — it does not parse
    locales, compute values, or perform any financial logic.

    The returned value bypasses auto-escaping because it may contain Typst
    markup for colored text.
    """
    s = str(value)
    escaped = str(typst_escape(s))
    if s.startswith("-"):
        return Markup(f'#text(fill: rgb("{negative_color}"))[{escaped}]')
    return Markup(escaped)


def typst_color(value: str, color: str) -> Markup:
    """Wrap a value in Typst colored text.

    Returns Typst markup like ``#text(fill: rgb("#27ae60"))[Above]``.
    The value is escaped before wrapping.
    """
    escaped = str(typst_escape(str(value)))
    return Markup(f'#text(fill: rgb("{color}"))[{escaped}]')


def typst_markup(value: str) -> Markup:
    """Mark a value as pre-escaped Typst markup — bypasses auto-escaping.

    **WARNING: This bypasses the text-interpolation safety layer.**

    Only use this for values that the template author controls and that
    intentionally contain Typst formatting.  Never use this for arbitrary
    user input.
    """
    return Markup(str(value))


FILTERS: dict[str, object] = {
    "typst_money": typst_money,
    "typst_color": typst_color,
    "typst_markup": typst_markup,
}
