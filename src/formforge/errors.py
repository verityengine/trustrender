"""Error types for Formforge.

Error classification
--------------------
Every error carries a stable ``code`` that identifies the failure category,
a ``stage`` that says where in the pipeline it occurred, the full diagnostic
from the underlying tool, and an optional ``source_path`` to the intermediate
``.typ`` file preserved for debugging.

Error codes
~~~~~~~~~~~
    INVALID_DATA         Bad input data (not a dict, bad JSON, wrong type)
    DATA_CONTRACT        Data does not satisfy the template's structural contract
    TEMPLATE_NOT_FOUND   Template file does not exist
    TEMPLATE_SYNTAX      Jinja2 syntax error in the template
    TEMPLATE_VARIABLE    Undefined variable during Jinja2 rendering
    MISSING_ASSET        Referenced file (image, etc.) not found during compile
    MISSING_FONT         Font not available during compile
    COMPILE_ERROR        Typst compilation failed (catch-all for Typst errors)
    RENDER_TIMEOUT       Render exceeded the time limit
    BACKEND_ERROR        Unexpected failure in the render backend

Stages
~~~~~~
    data_resolution      Resolving/parsing the data argument
    data_validation      Validating data against template contract
    template_preprocess  Jinja2 template rendering
    compilation          Typst compilation to PDF
    execution            Server/CLI execution wrapper
"""

from __future__ import annotations

from enum import Enum


class ErrorCode(str, Enum):
    """Stable error codes for Formforge failures."""

    INVALID_DATA = "INVALID_DATA"
    DATA_CONTRACT = "DATA_CONTRACT"
    TEMPLATE_NOT_FOUND = "TEMPLATE_NOT_FOUND"
    TEMPLATE_SYNTAX = "TEMPLATE_SYNTAX"
    TEMPLATE_VARIABLE = "TEMPLATE_VARIABLE"
    MISSING_ASSET = "MISSING_ASSET"
    MISSING_FONT = "MISSING_FONT"
    COMPILE_ERROR = "COMPILE_ERROR"
    RENDER_TIMEOUT = "RENDER_TIMEOUT"
    BACKEND_ERROR = "BACKEND_ERROR"


class FormforgeError(Exception):
    """Raised when a Formforge render fails.

    Attributes:
        code: Stable error code identifying the failure category.
        stage: Pipeline stage where the failure occurred.
        detail: Full diagnostic message from the underlying tool.
        source_path: Path to the intermediate .typ file (if preserved).
        template_path: Path to the original template file.
    """

    def __init__(
        self,
        message: str,
        *,
        code: ErrorCode = ErrorCode.BACKEND_ERROR,
        stage: str = "unknown",
        detail: str | None = None,
        source_path: str | None = None,
        template_path: str | None = None,
        validation_errors: list | None = None,
    ):
        self.code = code
        self.stage = stage
        self.detail = detail or message
        self.source_path = source_path
        self.template_path = template_path
        self.validation_errors = validation_errors

        # Build the user-facing message
        parts = [message]
        if source_path:
            parts.append(f"  Intermediate source: {source_path}")
        if template_path:
            parts.append(f"  Template: {template_path}")
        super().__init__("\n".join(parts))

    def to_dict(self, *, include_debug: bool = False) -> dict:
        """Serialize to a structured dict for JSON responses.

        Args:
            include_debug: If True, include source_path and full detail.
        """
        result: dict = {
            "error": self.code.value,
            "message": str(self).split("\n")[0],  # First line for summary
            "stage": self.stage,
        }
        if include_debug:
            result["detail"] = self.detail
            if self.source_path:
                result["source_path"] = self.source_path
            if self.template_path:
                result["template_path"] = self.template_path
        return result
