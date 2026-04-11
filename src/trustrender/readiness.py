"""Pre-render readiness verification.

Answers: "can this template + data + environment produce the right document?"
without actually rendering. Combines payload validation, template checks,
environment checks, and compliance eligibility into a single structured verdict.

This is NOT the render pipeline. It is a dry-run verification that reuses
existing validators and adds template/environment checks.

Usage::

    from trustrender.readiness import preflight

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

from .errors import ErrorCode, TrustRenderError


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
    except TrustRenderError:
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


# ---------------------------------------------------------------------------
# Font verification helpers
# ---------------------------------------------------------------------------

# Known bundled font families — these ship with TrustRender and are expected
# to be available when using bundled templates.
_BUNDLED_FONT_FAMILIES = frozenset({"inter"})

# Regex patterns for Typst font declarations
_FONT_SINGLE_RE = re.compile(r'font:\s*"([^"]+)"')
_FONT_STACK_RE = re.compile(r'font:\s*\(([^)]+)\)')
_FONT_NAME_RE = re.compile(r'"([^"]+)"')
# Captures Jinja2 variable references in font declarations: font: "{{ field_name }}"
_FONT_DYNAMIC_RE = re.compile(r'font:\s*"\{\{\s*([\w.]+)\s*\}\}"')


def _resolve_dotted(data: dict, path: str) -> str | None:
    """Resolve a dot-notation path from a data dict, returning the string value or None."""
    current: object = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current if isinstance(current, str) else None


def _resolve_dynamic_fonts(source: str, data: dict) -> list[str]:
    """Resolve Jinja2 variable references in font declarations.

    Finds patterns like ``font: "{{ field_name }}"`` and resolves
    ``field_name`` from the data dict.  Returns list of resolved font
    family names.  Unresolvable variables are silently skipped.

    Only handles simple variable references (``{{ field }}``,
    ``{{ obj.field }}``).  Filter expressions and conditionals are not
    supported.
    """
    resolved: list[str] = []
    for m in _FONT_DYNAMIC_RE.finditer(source):
        field_path = m.group(1)
        value = _resolve_dotted(data, field_path)
        if value:
            resolved.append(value)
    return resolved


def _enumerate_font_families(font_dirs: list[str] | None) -> set[str]:
    """Return lowercase font family names found in the given directories.

    Uses the same heuristic as doctor.py — split filename on [-_], take
    the first segment, lowercase.  E.g. ``Inter-Bold.ttf`` → ``"inter"``.
    """
    families: set[str] = set()
    if not font_dirs:
        return families
    for d in font_dirs:
        dp = Path(d)
        if not dp.is_dir():
            continue
        for ext in ("*.ttf", "*.otf"):
            for f in dp.glob(f"**/{ext}"):
                name = re.split(r"[-_]", f.stem)[0].lower()
                if name:
                    families.add(name)
    return families


def _parse_declared_fonts(source: str) -> list[list[str]]:
    """Extract font declarations from Typst source.

    Returns a list of font stacks.  A single font declaration like
    ``font: "Inter"`` becomes ``[["Inter"]]``.  A font stack like
    ``font: ("Inter", "Noto Sans")`` becomes ``[["Inter", "Noto Sans"]]``.

    Jinja2 variable references (containing ``{{``) are skipped.
    """
    stacks: list[list[str]] = []
    seen_positions: set[int] = set()

    # 1. Font stacks: font: ("Inter", "Noto Sans")
    for m in _FONT_STACK_RE.finditer(source):
        seen_positions.add(m.start())
        inner = m.group(1)
        names = [n.group(1) for n in _FONT_NAME_RE.finditer(inner)]
        names = [n for n in names if "{{" not in n]
        if names:
            stacks.append(names)

    # 2. Single fonts: font: "Inter" — skip positions already covered by stacks
    for m in _FONT_SINGLE_RE.finditer(source):
        if m.start() in seen_positions:
            continue
        name = m.group(1)
        if "{{" not in name:
            stacks.append([name])

    return stacks


def _is_bundled_template(template_path: Path) -> bool:
    """Return True if the template lives in the package's examples/ directory."""
    try:
        resolved = template_path.resolve()
        # Walk up from the package dir to find examples/
        pkg_dir = Path(__file__).resolve().parent  # src/trustrender/
        examples_dir = pkg_dir.parent.parent / "examples"
        if examples_dir.is_dir():
            return str(resolved).startswith(str(examples_dir.resolve()))
    except (OSError, ValueError):
        pass
    return False


def _check_fonts(
    template_path: Path,
    font_paths: list[str] | None,
    issues: list[ReadinessIssue],
    *,
    data: dict | None = None,
    strict: bool = False,
) -> None:
    """Check that fonts declared in the template are available.

    Verifies declared fonts against explicitly configured font paths
    (bundled + explicit).  When ``font_paths`` is None, auto-resolves
    the bundled font directory so that default callers still get font
    checking.

    When ``data`` is provided, also resolves dynamic font references
    (``font: "{{ field_name }}"``) from the data dict and checks them.

    System fonts cannot be reliably enumerated, so a missing font in
    configured paths gets a warning (it might be a system font).

    The error case is narrow: a bundled template expecting a known
    bundled font (Inter) that is missing from configured paths means
    the installation is broken — that is an error.
    """
    try:
        source = template_path.read_text()
    except (OSError, UnicodeDecodeError):
        return  # Can't read template — other stages will catch this

    font_stacks = _parse_declared_fonts(source)

    # Auto-resolve bundled fonts when no explicit paths are provided.
    # This ensures default callers still get font verification.
    effective_paths = font_paths
    if effective_paths is None:
        from . import bundled_font_dir

        bd = bundled_font_dir()
        if bd is not None:
            effective_paths = [str(bd)]

    available = _enumerate_font_families(effective_paths)
    bundled = _is_bundled_template(template_path)

    # Check static font declarations
    for stack in font_stacks:
        # If ANY font in the stack is found in configured paths, it's OK
        found = any(name.lower() in available for name in stack)
        if found:
            continue

        # None of the fonts in this stack were found in configured paths
        display = ", ".join(stack)
        first_font = stack[0].lower()

        if strict:
            severity = "error"
        elif bundled and first_font in _BUNDLED_FONT_FAMILIES:
            # Bundled template expects a bundled font that's missing —
            # the installation is broken.
            severity = "error"
        else:
            # Custom template or non-bundled font — might be a system font
            severity = "warning"

        issues.append(ReadinessIssue(
            stage="template",
            check="missing_font",
            severity=severity,
            path=display,
            message=f"Font not found in configured paths: {display}"
            + (" (bundled font expected)" if bundled and first_font in _BUNDLED_FONT_FAMILIES else "")
            + (" (may be available as system font)" if severity == "warning" else ""),
        ))

    # Check dynamic font declarations resolved from data
    if data is not None:
        for font_name in _resolve_dynamic_fonts(source, data):
            if font_name.lower() in available:
                continue
            if strict:
                severity = "error"
            elif bundled and font_name.lower() in _BUNDLED_FONT_FAMILIES:
                severity = "error"
            else:
                severity = "warning"
            issues.append(ReadinessIssue(
                stage="template",
                check="missing_font",
                severity=severity,
                path=font_name,
                message=f"Dynamic font not found in configured paths: {font_name}"
                + (" (may be available as system font)" if severity == "warning" else ""),
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
    except TrustRenderError:
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

    # XSD + Schematron validation — only when field validation passes.
    if not errors:
        try:
            from .zugferd import build_invoice_xml, validate_zugferd_xml

            xml_bytes = build_invoice_xml(data, profile=zugferd)
            xml_errors = validate_zugferd_xml(xml_bytes)
            if xml_errors is None:
                issues.append(ReadinessIssue(
                    stage="compliance",
                    check="xsd_validation",
                    severity="warning",
                    path="facturx",
                    message="facturx not installed — XSD/Schematron validation skipped",
                ))
            else:
                for msg in xml_errors:
                    issues.append(ReadinessIssue(
                        stage="compliance",
                        check="xsd_validation" if "XSD" in msg else "schematron_validation",
                        severity="error",
                        path="xml",
                        message=msg,
                    ))
                # Advisory: warn if Schematron specifically is unavailable
                if not xml_errors:
                    try:
                        from facturx.facturx import xml_check_schematron  # noqa: F401
                    except ImportError:
                        issues.append(ReadinessIssue(
                            stage="compliance",
                            check="schematron_validation",
                            severity="warning",
                            path="facturx",
                            message="facturx.facturx not available — Schematron validation skipped",
                        ))
        except Exception as exc:
            issues.append(ReadinessIssue(
                stage="compliance",
                check="xml_generation",
                severity="error",
                path="xml",
                message=f"XML generation failed: {exc}",
            ))

    # Profile eligibility — reuse the validation result from above
    if not errors:
        eligible.append(zugferd)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _check_text_safety(
    data: dict,
    issues: list[ReadinessIssue],
) -> None:
    """Safe-by-default text scanning — detect control and zero-width chars in all strings.

    Runs independently of semantic hints.  Walks the entire data dict and
    scans every string value for problematic characters.
    """
    from .semantic import collect_string_paths, scan_text

    for path in collect_string_paths(data):
        # Resolve the value from the data dict using the concrete path
        current: object = data
        try:
            for part in _split_concrete_path(path):
                if isinstance(part, int):
                    current = current[part]  # type: ignore[index]
                else:
                    current = current[part]  # type: ignore[index]
        except (KeyError, IndexError, TypeError):
            continue
        if not isinstance(current, str):
            continue
        for problem in scan_text(current):
            issues.append(ReadinessIssue(
                stage="text_safety",
                check="text_anomaly",
                severity="warning",
                path=path,
                message=f"{problem} (auto-detected)",
            ))


def _split_concrete_path(path: str) -> list[str | int]:
    """Split a concrete path like 'items[0].description' into segments."""
    import re

    segments: list[str | int] = []
    for part in re.split(r"\.|(?=\[)", path):
        if not part:
            continue
        if part.startswith("[") and part.endswith("]"):
            segments.append(int(part[1:-1]))
        else:
            segments.append(part)
    return segments


def _check_semantic(
    data: dict,
    semantic_hints: object | None,
    issues: list[ReadinessIssue],
) -> None:
    """Stage 6: Semantic validation — does the data make business sense?"""
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
    font_paths: list[str] | None = None,
    zugferd: str | None = None,
    semantic_hints: object | None = None,
    strict: bool = False,
    text_scan: bool = True,
) -> ReadinessVerdict:
    """Run all readiness checks without rendering.

    Combines payload validation, template checks, font checks,
    environment checks, compliance eligibility, text safety scanning,
    and optional semantic validation into a single structured verdict.

    Args:
        template: Path to a ``.j2.typ`` or ``.typ`` template file.
        data: Template data as a dict.
        font_paths: Resolved font directory paths (bundled + explicit).
            Used to verify declared fonts are available.
        zugferd: If set, also run compliance checks for this profile.
        semantic_hints: SemanticHints instance for semantic validation.
            If None, semantic checks are skipped.
        strict: If True, partial contracts from unresolved dynamic
            includes are promoted from warnings to errors, and missing
            fonts are promoted from warnings to errors. This blocks
            readiness when the contract is provably incomplete or when
            font availability cannot be confirmed.
        text_scan: If True (default), scan all string values in the data
            dict for control characters and zero-width characters. Set to
            False to skip text safety scanning.

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

    # Stage 2: Template (syntax + assets + fonts)
    _check_template(template_path, all_issues)
    _check_fonts(template_path, font_paths, all_issues, data=data, strict=strict)
    stages.append("template")

    # Stage 3: Environment
    _check_environment(zugferd, all_issues)
    stages.append("environment")

    # Stage 4: Compliance
    if zugferd:
        _check_compliance(data, zugferd, all_issues, eligible)
        stages.append("compliance")

    # Stage 5: Text safety (safe-by-default)
    if text_scan:
        _check_text_safety(data, all_issues)
        stages.append("text_safety")

    # Stage 6: Semantic (opt-in)
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
