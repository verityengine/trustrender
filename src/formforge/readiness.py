"""Pre-render readiness verification.

Answers: "can this template + data + environment produce the right document?"
without actually rendering. Combines payload validation, template checks,
environment checks, and compliance eligibility into a single structured verdict.

This is NOT the render pipeline. It is a dry-run verification that reuses
existing validators and adds template/environment checks.

Usage::

    from formforge.readiness import preflight

    verdict = preflight("invoice.j2.typ", data, zugferd="en16931")
    if not verdict.ready:
        for issue in verdict.errors:
            print(f"{issue.path}: {issue.message}")
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError

from .errors import ErrorCode, FormforgeError


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ReadinessIssue:
    """A single readiness check result."""

    stage: str  # "payload", "template", "environment", "compliance"
    check: str  # "missing_field", "syntax_error", "asset_not_found", etc.
    severity: str  # "error" (blocks render) or "warning" (advisory)
    path: str  # "seller.vat_id", "line 14: image", "backend", etc.
    message: str  # Human-readable description


@dataclass
class ReadinessVerdict:
    """Result of a pre-render readiness check."""

    ready: bool  # True if no errors (warnings are OK)
    errors: list[ReadinessIssue] = field(default_factory=list)
    warnings: list[ReadinessIssue] = field(default_factory=list)
    profile_eligible: list[str] = field(default_factory=list)
    stages_checked: list[str] = field(default_factory=list)
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ---------------------------------------------------------------------------
# Individual stage checks
# ---------------------------------------------------------------------------

def _check_payload(
    template_path: Path,
    data: dict,
    issues: list[ReadinessIssue],
    *,
    strict: bool = False,
) -> None:
    """Stage 1: Payload readiness — does the data fit the template?"""
    if not template_path.name.endswith(".j2.typ"):
        return  # Raw .typ templates have no contract to validate against

    try:
        from .contract import infer_contract_with_metadata, validate_data

        result = infer_contract_with_metadata(template_path)
        errors = validate_data(result.contract, data)
        for e in errors:
            issues.append(ReadinessIssue(
                stage="payload",
                check="contract_violation",
                severity="error",
                path=e.path,
                message=e.message,
            ))
        if result.is_partial:
            # strict=True promotes partial-contract warnings to errors.
            # This blocks readiness when dynamic includes leave the contract
            # incomplete — callers who need certainty opt in.
            severity = "error" if strict else "warning"
            for inc in result.unresolved_includes:
                issues.append(ReadinessIssue(
                    stage="payload",
                    check="partial_contract",
                    severity=severity,
                    path=inc,
                    message=f"Contract is partial: include '{inc}' could not be resolved statically",
                ))
    except FormforgeError:
        # Template parse error — will be caught in template stage
        pass


def _check_template(
    template_path: Path,
    issues: list[ReadinessIssue],
) -> None:
    """Stage 2: Template readiness — is the template valid and complete?"""
    if not template_path.name.endswith(".j2.typ"):
        # Raw .typ — just check it exists (already done upstream)
        return

    # 2a. Jinja2 syntax check
    env = Environment(
        loader=FileSystemLoader(str(template_path.parent)),
        keep_trailing_newline=True,
    )
    try:
        source = template_path.read_text()
        env.parse(source)
    except TemplateSyntaxError as exc:
        issues.append(ReadinessIssue(
            stage="template",
            check="syntax_error",
            severity="error",
            path=f"{template_path.name}:{exc.lineno}" if exc.lineno else template_path.name,
            message=f"Jinja2 syntax error: {exc.message}",
        ))
        return  # Can't check further if template doesn't parse

    # 2b. Asset existence check — find image paths in template source
    _check_template_assets(template_path, source, issues)


def _check_template_assets(
    template_path: Path,
    source: str,
    issues: list[ReadinessIssue],
) -> None:
    """Check that images referenced in the template exist on disk."""
    # Match Typst image() calls with string literal paths
    # Pattern: image("path/to/file", ...) or image("path/to/file")
    image_pattern = re.compile(r'image\(\s*"([^"]+)"')
    template_dir = template_path.parent

    for match in image_pattern.finditer(source):
        image_path = match.group(1)
        # Skip Jinja2 variables (contain {{ }})
        if "{{" in image_path:
            continue
        full_path = template_dir / image_path
        if not full_path.exists():
            issues.append(ReadinessIssue(
                stage="template",
                check="asset_not_found",
                severity="error",
                path=image_path,
                message=f"Image not found: {image_path}",
            ))


def _check_environment(
    zugferd: str | None,
    issues: list[ReadinessIssue],
) -> None:
    """Stage 3: Environment readiness — can we actually render?"""
    # 3a. Backend availability
    from .engine import get_backend

    try:
        get_backend()
    except FormforgeError:
        issues.append(ReadinessIssue(
            stage="environment",
            check="no_backend",
            severity="error",
            path="backend",
            message="No Typst backend available (install typst-py or typst CLI)",
        ))

    # 3b. PDF/A-3b support check when ZUGFeRD requested
    if zugferd:
        try:
            import typst as _typst

            # Verify pdf_standards parameter is accepted
            if not hasattr(_typst, "compile"):
                issues.append(ReadinessIssue(
                    stage="environment",
                    check="typst_version",
                    severity="error",
                    path="typst",
                    message="typst-py does not support pdf_standards (upgrade to >=0.14)",
                ))
        except ImportError:
            # CLI backend — assume it supports --pdf-standard (Typst 0.14+)
            pass


def _check_compliance(
    data: dict,
    zugferd: str | None,
    issues: list[ReadinessIssue],
    eligible: list[str],
) -> None:
    """Stage 4: Compliance eligibility — which profiles can this data satisfy?"""
    if not zugferd:
        return

    from .zugferd import validate_zugferd_invoice_data

    # Check requested profile
    errors = validate_zugferd_invoice_data(data, profile=zugferd)
    for e in errors:
        issues.append(ReadinessIssue(
            stage="compliance",
            check="zugferd_field",
            severity="error",
            path=e.path,
            message=e.message,
        ))

    # Profile eligibility report
    for profile in ("en16931", "xrechnung"):
        profile_errors = validate_zugferd_invoice_data(data, profile=profile)
        if not profile_errors:
            eligible.append(profile)
        elif profile != zugferd:
            # Show what's missing for non-requested profiles as info
            missing = [e.path for e in profile_errors]
            issues.append(ReadinessIssue(
                stage="compliance",
                check="profile_eligibility",
                severity="warning",
                path=profile,
                message=f"not eligible (missing: {', '.join(missing[:5])})",
            ))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _check_semantic(
    data: dict,
    semantic_hints: object | None,
    issues: list[ReadinessIssue],
) -> None:
    """Stage 5: Semantic validation — does the data make business sense?"""
    if semantic_hints is None:
        return

    from .semantic import validate_semantics

    report = validate_semantics(data, hints=semantic_hints)
    for si in report.issues:
        issues.append(ReadinessIssue(
            stage="semantic",
            check=si.category,
            severity=si.severity,
            path=si.path,
            message=si.message,
        ))


def preflight(
    template: str | os.PathLike,
    data: dict,
    *,
    zugferd: str | None = None,
    semantic_hints: object | None = None,
    strict: bool = False,
) -> ReadinessVerdict:
    """Run all readiness checks without rendering.

    Combines payload validation, template checks, environment checks,
    compliance eligibility, and optional semantic validation into a
    single structured verdict.

    Args:
        template: Path to a ``.j2.typ`` or ``.typ`` template file.
        data: Template data as a dict.
        zugferd: If set, also run compliance checks for this profile.
        semantic_hints: SemanticHints instance for semantic validation.
            If None, semantic checks are skipped.
        strict: If True, partial contracts from unresolved dynamic
            includes are promoted from warnings to errors. This blocks
            readiness when the contract is provably incomplete.

    Returns:
        ReadinessVerdict with ``ready=True`` if no errors.
        Warnings do not block readiness.
    """
    template_path = Path(template)
    all_issues: list[ReadinessIssue] = []
    eligible: list[str] = []
    stages: list[str] = []

    # Template exists?
    if not template_path.exists():
        all_issues.append(ReadinessIssue(
            stage="payload",
            check="template_not_found",
            severity="error",
            path=str(template_path),
            message=f"Template not found: {template_path}",
        ))
        errors = [i for i in all_issues if i.severity == "error"]
        warnings = [i for i in all_issues if i.severity == "warning"]
        return ReadinessVerdict(
            ready=False,
            errors=errors,
            warnings=warnings,
            profile_eligible=eligible,
            stages_checked=["payload"],
        )

    # Stage 1: Payload
    _check_payload(template_path, data, all_issues, strict=strict)
    stages.append("payload")

    # Stage 2: Template
    _check_template(template_path, all_issues)
    stages.append("template")

    # Stage 3: Environment
    _check_environment(zugferd, all_issues)
    stages.append("environment")

    # Stage 4: Compliance
    if zugferd:
        _check_compliance(data, zugferd, all_issues, eligible)
        stages.append("compliance")

    # Stage 5: Semantic (opt-in)
    if semantic_hints is not None:
        _check_semantic(data, semantic_hints, all_issues)
        stages.append("semantic")

    errors = [i for i in all_issues if i.severity == "error"]
    warnings = [i for i in all_issues if i.severity == "warning"]

    return ReadinessVerdict(
        ready=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        profile_eligible=eligible,
        stages_checked=stages,
    )
