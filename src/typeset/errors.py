"""Error types for Typeset."""

from __future__ import annotations


class TypesetError(Exception):
    """Raised when a Typeset render fails.

    Attributes:
        source_path: Path to the intermediate .typ file (if preserved).
            Inspect this file to debug template issues.
    """

    def __init__(self, message: str, *, source_path: str | None = None):
        self.source_path = source_path
        parts = [message]
        if source_path:
            parts.append(f"  Rendered source preserved at: {source_path}")
        super().__init__("\n".join(parts))
