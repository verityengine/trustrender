"""Baseline drift detection for rendered documents.

Compares measurable outputs of a current render against a stored baseline:
render success, page count, file size, and compliance status.

This is NOT rich document regression — it is deterministic comparison on
measurable outputs. Source-level and section-level regression require
source maps and anchors (deferred).

Baselines are stored as JSON files on disk. No database required.

Usage::

    from trustrender.regression import save_baseline, check_drift

    # After a known-good render:
    save_baseline(baseline_dir, template_name, fingerprint, pdf_bytes)

    # Later, compare:
    result = check_drift(baseline_dir, template_name, fingerprint, pdf_bytes)
    if result.has_errors:
        for f in result.findings:
            print(f"{f.check_name}: {f.message}")
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from typing import Literal

from .fingerprint import InputFingerprint

# Baseline schema version — increment when the baseline format changes.
_SCHEMA_VERSION = 2


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DriftBaseline:
    """Stored baseline for drift comparison.

    Stored as JSON on disk. The ``schema_version`` field allows future
    migration of baseline files without ambiguity.
    """

    schema_version: int
    baseline_id: str
    created_at: str                          # ISO 8601
    template_file: str
    trustrender_version: str

    # Input fingerprint (serialized)
    fingerprint_json: dict

    # Output characteristics
    pdf_size: int                            # Bytes
    page_count: int | None                   # From pypdf if available
    render_success: bool
    render_duration_ms: int | None           # Wall clock, advisory only

    # Compliance status
    zugferd_valid: bool | None               # None if not applicable
    contract_valid: bool | None              # None if not applicable

    # Semantic baseline
    semantic_issue_count: int

    # Embedded font names from PDF (None if extraction failed or old baseline)
    embedded_fonts: list[str] | None = None

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "baseline_id": self.baseline_id,
            "created_at": self.created_at,
            "template_file": self.template_file,
            "trustrender_version": self.trustrender_version,
            "fingerprint_json": self.fingerprint_json,
            "pdf_size": self.pdf_size,
            "page_count": self.page_count,
            "render_success": self.render_success,
            "render_duration_ms": self.render_duration_ms,
            "zugferd_valid": self.zugferd_valid,
            "contract_valid": self.contract_valid,
            "semantic_issue_count": self.semantic_issue_count,
            "embedded_fonts": self.embedded_fonts,
        }

    @classmethod
    def from_dict(cls, d: dict) -> DriftBaseline:
        return cls(
            schema_version=d.get("schema_version", 1),
            baseline_id=d["baseline_id"],
            created_at=d["created_at"],
            template_file=d["template_file"],
            trustrender_version=d.get("trustrender_version", "unknown"),
            fingerprint_json=d["fingerprint_json"],
            pdf_size=d["pdf_size"],
            page_count=d.get("page_count"),
            render_success=d["render_success"],
            render_duration_ms=d.get("render_duration_ms"),
            zugferd_valid=d.get("zugferd_valid"),
            contract_valid=d.get("contract_valid"),
            semantic_issue_count=d.get("semantic_issue_count", 0),
            embedded_fonts=d.get("embedded_fonts"),
        )


@dataclass
class DriftFinding:
    """One specific drift finding."""

    check_name: str
    severity: Literal["error", "warning", "info"]
    category: Literal["structure", "size", "compliance", "semantic"]
    message: str
    baseline_value: str | None
    current_value: str | None
    deterministic: bool                      # True = exact comparison
    confidence: Literal["high", "medium", "low"]


@dataclass
class DriftResult:
    """Complete result of drift comparison."""

    baseline_id: str
    findings: list[DriftFinding] = field(default_factory=list)
    checks_run: list[str] = field(default_factory=list)
    checked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    @property
    def has_errors(self) -> bool:
        return any(f.severity == "error" for f in self.findings)

    @property
    def has_warnings(self) -> bool:
        return any(f.severity == "warning" for f in self.findings)

    @property
    def passed(self) -> bool:
        return not self.has_errors

    def to_dict(self) -> dict:
        return {
            "baseline_id": self.baseline_id,
            "passed": self.passed,
            "findings": [
                {
                    "check_name": f.check_name,
                    "severity": f.severity,
                    "category": f.category,
                    "message": f.message,
                    "baseline_value": f.baseline_value,
                    "current_value": f.current_value,
                    "deterministic": f.deterministic,
                    "confidence": f.confidence,
                }
                for f in self.findings
            ],
            "checks_run": self.checks_run,
            "checked_at": self.checked_at,
        }


# ---------------------------------------------------------------------------
# PDF page count helper
# ---------------------------------------------------------------------------

def _get_page_count(pdf_bytes: bytes) -> int | None:
    """Extract page count from PDF bytes using pypdf."""
    try:
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(pdf_bytes))
        return len(reader.pages)
    except Exception:
        return None


def _extract_embedded_fonts(pdf_bytes: bytes) -> set[str] | None:
    """Extract embedded font family names from PDF bytes.

    Walks each page's ``/Resources`` → ``/Font`` → ``/BaseFont`` entries.
    Strips 6-char subset prefixes (e.g. ``ABCDEF+Inter-Regular`` →
    ``Inter-Regular``) and leading slashes.

    Returns a set of font names, or *None* if extraction fails or the PDF
    contains no font resources.
    """
    try:
        from pypdf import PdfReader

        reader = PdfReader(BytesIO(pdf_bytes))
        fonts: set[str] = set()
        for page in reader.pages:
            resources = page.get("/Resources")
            if resources is None:
                continue
            font_dict = resources.get("/Font")
            if font_dict is None:
                continue
            for font_ref in font_dict.values():
                font_obj = (
                    font_ref.get_object()
                    if hasattr(font_ref, "get_object")
                    else font_ref
                )
                base_font = font_obj.get("/BaseFont")
                if base_font is None:
                    continue
                name = str(base_font)
                if name.startswith("/"):
                    name = name[1:]
                # Strip subset prefix (e.g. "ABCDEF+Inter-Regular")
                if "+" in name:
                    prefix, rest = name.split("+", 1)
                    if len(prefix) == 6 and prefix.isalpha():
                        name = rest
                fonts.add(name)
        return fonts if fonts else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Drift checks
# ---------------------------------------------------------------------------

def _check_render_success(
    baseline: DriftBaseline,
    render_success: bool,
    findings: list[DriftFinding],
) -> None:
    """Check if render success status changed."""
    if baseline.render_success and not render_success:
        findings.append(DriftFinding(
            check_name="render_success",
            severity="error",
            category="structure",
            message="Render now fails (was successful in baseline)",
            baseline_value="success",
            current_value="failure",
            deterministic=True,
            confidence="high",
        ))
    elif not baseline.render_success and render_success:
        findings.append(DriftFinding(
            check_name="render_success",
            severity="info",
            category="structure",
            message="Render now succeeds (was failing in baseline)",
            baseline_value="failure",
            current_value="success",
            deterministic=True,
            confidence="high",
        ))


def _check_page_count(
    baseline: DriftBaseline,
    current_page_count: int | None,
    findings: list[DriftFinding],
) -> None:
    """Check if page count changed."""
    if baseline.page_count is None or current_page_count is None:
        return

    diff = current_page_count - baseline.page_count
    if diff == 0:
        return

    abs_diff = abs(diff)
    direction = "increased" if diff > 0 else "decreased"

    if abs_diff > 3:
        severity: Literal["error", "warning", "info"] = "error"
    elif abs_diff > 0:
        severity = "warning"
    else:
        return

    findings.append(DriftFinding(
        check_name="page_count_change",
        severity=severity,
        category="structure",
        message=f"Page count {direction} by {abs_diff} (baseline: {baseline.page_count}, current: {current_page_count})",
        baseline_value=str(baseline.page_count),
        current_value=str(current_page_count),
        deterministic=True,
        confidence="high",
    ))


def _check_file_size(
    baseline: DriftBaseline,
    current_size: int,
    findings: list[DriftFinding],
) -> None:
    """Check if PDF file size changed significantly."""
    if baseline.pdf_size == 0:
        return

    ratio = current_size / baseline.pdf_size
    pct_change = abs(ratio - 1.0) * 100

    if pct_change > 50:
        findings.append(DriftFinding(
            check_name="file_size_spike",
            severity="error",
            category="size",
            message=f"PDF size changed by {pct_change:.0f}% (baseline: {baseline.pdf_size} bytes, current: {current_size} bytes)",
            baseline_value=str(baseline.pdf_size),
            current_value=str(current_size),
            deterministic=True,
            confidence="high",
        ))
    elif pct_change > 20:
        findings.append(DriftFinding(
            check_name="file_size_drift",
            severity="warning",
            category="size",
            message=f"PDF size changed by {pct_change:.0f}% (baseline: {baseline.pdf_size} bytes, current: {current_size} bytes)",
            baseline_value=str(baseline.pdf_size),
            current_value=str(current_size),
            deterministic=True,
            confidence="high",
        ))


def _check_contract_status(
    baseline: DriftBaseline,
    contract_valid: bool | None,
    findings: list[DriftFinding],
) -> None:
    """Check if contract validation status changed."""
    if baseline.contract_valid is None or contract_valid is None:
        return

    if baseline.contract_valid and not contract_valid:
        findings.append(DriftFinding(
            check_name="contract_status_change",
            severity="error",
            category="compliance",
            message="Contract validation now fails (was passing in baseline)",
            baseline_value="valid",
            current_value="invalid",
            deterministic=True,
            confidence="high",
        ))


def _check_zugferd_status(
    baseline: DriftBaseline,
    zugferd_valid: bool | None,
    findings: list[DriftFinding],
) -> None:
    """Check if ZUGFeRD validation status changed."""
    if baseline.zugferd_valid is None or zugferd_valid is None:
        return

    if baseline.zugferd_valid and not zugferd_valid:
        findings.append(DriftFinding(
            check_name="zugferd_status_change",
            severity="error",
            category="compliance",
            message="ZUGFeRD validation now fails (was passing in baseline)",
            baseline_value="valid",
            current_value="invalid",
            deterministic=True,
            confidence="high",
        ))


def _check_embedded_fonts(
    baseline: DriftBaseline,
    current_fonts: set[str] | None,
    findings: list[DriftFinding],
) -> None:
    """Check if embedded font set changed."""
    if baseline.embedded_fonts is None or current_fonts is None:
        return

    baseline_set = set(baseline.embedded_fonts)
    if baseline_set == current_fonts:
        return

    removed = baseline_set - current_fonts
    added = current_fonts - baseline_set

    parts = []
    if removed:
        parts.append(f"removed {', '.join(sorted(removed))}")
    if added:
        parts.append(f"added {', '.join(sorted(added))}")

    findings.append(DriftFinding(
        check_name="embedded_fonts_changed",
        severity="warning",
        category="structure",
        message=f"Embedded fonts changed: {'; '.join(parts)}",
        baseline_value=", ".join(sorted(baseline_set)),
        current_value=", ".join(sorted(current_fonts)),
        deterministic=True,
        confidence="high",
    ))


# ---------------------------------------------------------------------------
# Baseline storage
# ---------------------------------------------------------------------------

def _baseline_dir_for_template(
    baseline_dir: Path,
    template_name: str,
) -> Path:
    """Get the baseline directory for a specific template."""
    # Sanitize template name for filesystem
    safe_name = template_name.replace("/", "_").replace("\\", "_")
    return baseline_dir / safe_name


def save_baseline(
    baseline_dir: str | os.PathLike,
    template_name: str,
    fingerprint: InputFingerprint,
    pdf_bytes: bytes,
    *,
    render_duration_ms: int | None = None,
    zugferd_valid: bool | None = None,
    contract_valid: bool | None = None,
    semantic_issue_count: int = 0,
) -> DriftBaseline:
    """Save a new baseline after a successful render.

    Creates a JSON file in ``baseline_dir/<template_name>/latest.json``.

    Args:
        baseline_dir: Root directory for all baselines.
        template_name: Template filename (used as subdirectory name).
        fingerprint: InputFingerprint from the render.
        pdf_bytes: The rendered PDF bytes.
        render_duration_ms: Optional render time in milliseconds.
        zugferd_valid: Whether ZUGFeRD validation passed (None if N/A).
        contract_valid: Whether contract validation passed (None if N/A).
        semantic_issue_count: Number of semantic issues found.

    Returns:
        The saved DriftBaseline.
    """
    baseline_dir = Path(baseline_dir)
    template_dir = _baseline_dir_for_template(baseline_dir, template_name)
    template_dir.mkdir(parents=True, exist_ok=True)

    page_count = _get_page_count(pdf_bytes)
    fonts_set = _extract_embedded_fonts(pdf_bytes)
    embedded_fonts = sorted(fonts_set) if fonts_set else None
    now = datetime.now(timezone.utc).isoformat()

    baseline = DriftBaseline(
        schema_version=_SCHEMA_VERSION,
        baseline_id=f"{template_name}:{now}",
        created_at=now,
        template_file=template_name,
        trustrender_version=fingerprint.trustrender_version,
        fingerprint_json=fingerprint.to_dict(),
        pdf_size=len(pdf_bytes),
        page_count=page_count,
        render_success=True,
        render_duration_ms=render_duration_ms,
        zugferd_valid=zugferd_valid,
        contract_valid=contract_valid,
        semantic_issue_count=semantic_issue_count,
        embedded_fonts=embedded_fonts,
    )

    # Write latest
    latest_path = template_dir / "latest.json"
    latest_path.write_text(
        json.dumps(baseline.to_dict(), indent=2, ensure_ascii=False) + "\n"
    )

    return baseline


def load_baseline(
    baseline_dir: str | os.PathLike,
    template_name: str,
) -> DriftBaseline | None:
    """Load the latest baseline for a template.

    Returns None if no baseline exists.
    """
    baseline_dir = Path(baseline_dir)
    template_dir = _baseline_dir_for_template(baseline_dir, template_name)
    latest_path = template_dir / "latest.json"

    if not latest_path.exists():
        return None

    try:
        d = json.loads(latest_path.read_text())
        return DriftBaseline.from_dict(d)
    except (json.JSONDecodeError, KeyError):
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def check_drift(
    baseline_dir: str | os.PathLike,
    template_name: str,
    fingerprint: InputFingerprint,
    pdf_bytes: bytes,
    *,
    render_success: bool = True,
    zugferd_valid: bool | None = None,
    contract_valid: bool | None = None,
    semantic_issue_count: int = 0,
) -> DriftResult | None:
    """Compare a current render against the stored baseline.

    Args:
        baseline_dir: Root directory for all baselines.
        template_name: Template filename to look up baseline for.
        fingerprint: InputFingerprint from the current render.
        pdf_bytes: The current rendered PDF bytes.
        render_success: Whether the current render succeeded.
        zugferd_valid: Whether ZUGFeRD validation passed (None if N/A).
        contract_valid: Whether contract validation passed (None if N/A).
        semantic_issue_count: Number of semantic issues found.

    Returns:
        DriftResult with findings, or None if no baseline exists.
    """
    baseline = load_baseline(baseline_dir, template_name)
    if baseline is None:
        return None

    findings: list[DriftFinding] = []
    checks_run: list[str] = []

    # Run all checks
    _check_render_success(baseline, render_success, findings)
    checks_run.append("render_success")

    if render_success:
        current_page_count = _get_page_count(pdf_bytes)
        _check_page_count(baseline, current_page_count, findings)
        checks_run.append("page_count_change")

        _check_file_size(baseline, len(pdf_bytes), findings)
        checks_run.extend(["file_size_drift", "file_size_spike"])

        current_fonts = _extract_embedded_fonts(pdf_bytes)
        _check_embedded_fonts(baseline, current_fonts, findings)
        checks_run.append("embedded_fonts_changed")

    _check_contract_status(baseline, contract_valid, findings)
    checks_run.append("contract_status_change")

    _check_zugferd_status(baseline, zugferd_valid, findings)
    checks_run.append("zugferd_status_change")

    return DriftResult(
        baseline_id=baseline.baseline_id,
        findings=findings,
        checks_run=checks_run,
    )
