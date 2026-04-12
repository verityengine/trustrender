"""Input fingerprinting and change detection.

Computes a cryptographic identity of every input to a render call:
template, includes, assets, fonts, data, config, and environment.

Two renders with the same InputFingerprint should produce identical output
(modulo non-determinism in Typst itself, which is minimal).

Change detection compares two fingerprints and produces a ChangeSet
describing exactly what is different.

Usage::

    from trustrender.fingerprint import compute_fingerprint, compare

    fp = compute_fingerprint(template_path, data, font_paths=fonts)
    # Later, compare against a baseline:
    changes = compare(baseline_fp, current_fp, baseline_data, current_data)
    if changes.has_changes:
        for c in changes.data_changes:
            print(f"{c.path}: {c.change_type}")
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from . import __version__


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FileHash:
    """Hash of a single file with size for quick comparison."""

    path: str       # Relative to template dir (or absolute for fonts)
    sha256: str     # "sha256:<hex>"
    size: int       # Bytes


@dataclass(frozen=True)
class InputFingerprint:
    """Cryptographic identity of all inputs to a single render call.

    Two renders with the same InputFingerprint should produce identical
    output.
    """

    # Content hashes
    template_hash: FileHash
    include_hashes: tuple[FileHash, ...]     # Sorted by path
    asset_hashes: tuple[FileHash, ...]       # Sorted by path
    font_hashes: tuple[FileHash, ...]        # Sorted by path
    data_hash: str                           # "sha256:<hex>" of canonical JSON

    # Configuration
    backend: str                             # "typst-py" or "typst-cli"
    zugferd_profile: str | None
    provenance_enabled: bool
    validate_enabled: bool

    # Environment
    trustrender_version: str
    typst_version: str

    # Computed identity
    fingerprint: str                         # SHA-256 of all above
    created_at: str                          # ISO 8601

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict."""
        return {
            "template_hash": _file_hash_to_dict(self.template_hash),
            "include_hashes": [_file_hash_to_dict(h) for h in self.include_hashes],
            "asset_hashes": [_file_hash_to_dict(h) for h in self.asset_hashes],
            "font_hashes": [_file_hash_to_dict(h) for h in self.font_hashes],
            "data_hash": self.data_hash,
            "backend": self.backend,
            "zugferd_profile": self.zugferd_profile,
            "provenance_enabled": self.provenance_enabled,
            "validate_enabled": self.validate_enabled,
            "trustrender_version": self.trustrender_version,
            "typst_version": self.typst_version,
            "fingerprint": self.fingerprint,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict) -> InputFingerprint:
        """Deserialize from a dict."""
        return cls(
            template_hash=_file_hash_from_dict(d["template_hash"]),
            include_hashes=tuple(_file_hash_from_dict(h) for h in d["include_hashes"]),
            asset_hashes=tuple(_file_hash_from_dict(h) for h in d["asset_hashes"]),
            font_hashes=tuple(_file_hash_from_dict(h) for h in d["font_hashes"]),
            data_hash=d["data_hash"],
            backend=d["backend"],
            zugferd_profile=d.get("zugferd_profile"),
            provenance_enabled=d["provenance_enabled"],
            validate_enabled=d["validate_enabled"],
            trustrender_version=d["trustrender_version"],
            typst_version=d["typst_version"],
            fingerprint=d["fingerprint"],
            created_at=d["created_at"],
        )


# ---------------------------------------------------------------------------
# Change types
# ---------------------------------------------------------------------------

@dataclass
class FieldChange:
    """One changed field in the data payload between two renders."""

    path: str                                    # "items[3].unit_price"
    change_type: Literal["added", "removed", "modified"]
    old_value: str | None                        # JSON repr, truncated
    new_value: str | None                        # JSON repr, truncated


@dataclass
class FileChange:
    """One changed file (template, asset, font) between two renders."""

    path: str
    change_type: Literal["added", "removed", "modified"]
    old_hash: str | None
    new_hash: str | None


@dataclass
class ConfigChange:
    """One changed config parameter between two renders."""

    key: str
    old_value: str | None
    new_value: str | None


@dataclass
class ChangeSet:
    """Complete diff between two InputFingerprints."""

    baseline_fingerprint: str
    current_fingerprint: str
    data_changes: list[FieldChange] = field(default_factory=list)
    template_changes: list[FileChange] = field(default_factory=list)
    asset_changes: list[FileChange] = field(default_factory=list)
    font_changes: list[FileChange] = field(default_factory=list)
    config_changes: list[ConfigChange] = field(default_factory=list)
    environment_changes: list[ConfigChange] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(
            self.data_changes or self.template_changes or self.asset_changes
            or self.font_changes or self.config_changes or self.environment_changes
        )

    @property
    def change_categories(self) -> list[str]:
        """Which categories have changes."""
        categories = []
        if self.data_changes:
            categories.append("data")
        if self.template_changes:
            categories.append("template")
        if self.asset_changes:
            categories.append("assets")
        if self.font_changes:
            categories.append("fonts")
        if self.config_changes:
            categories.append("config")
        if self.environment_changes:
            categories.append("environment")
        return categories

    def to_dict(self) -> dict:
        """Serialize to a JSON-compatible dict."""
        return {
            "baseline_fingerprint": self.baseline_fingerprint,
            "current_fingerprint": self.current_fingerprint,
            "data_changes": [
                {"path": c.path, "change_type": c.change_type,
                 "old_value": c.old_value, "new_value": c.new_value}
                for c in self.data_changes
            ],
            "template_changes": [
                {"path": c.path, "change_type": c.change_type,
                 "old_hash": c.old_hash, "new_hash": c.new_hash}
                for c in self.template_changes
            ],
            "asset_changes": [
                {"path": c.path, "change_type": c.change_type,
                 "old_hash": c.old_hash, "new_hash": c.new_hash}
                for c in self.asset_changes
            ],
            "font_changes": [
                {"path": c.path, "change_type": c.change_type,
                 "old_hash": c.old_hash, "new_hash": c.new_hash}
                for c in self.font_changes
            ],
            "config_changes": [
                {"path": c.key, "change_type": "modified",
                 "old_value": c.old_value, "new_value": c.new_value}
                for c in self.config_changes
            ],
            "environment_changes": [
                {"path": c.key, "change_type": "modified",
                 "old_value": c.old_value, "new_value": c.new_value}
                for c in self.environment_changes
            ],
        }


# ---------------------------------------------------------------------------
# Hashing helpers (reuse patterns from provenance.py)
# ---------------------------------------------------------------------------

def _hash_bytes(data: bytes) -> str:
    """SHA-256 hash of raw bytes."""
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _canonical_json(data: dict) -> bytes:
    """Canonical JSON for deterministic hashing."""
    return json.dumps(
        data, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode()


def _hash_file(path: Path) -> FileHash:
    """Hash a single file."""
    content = path.read_bytes()
    return FileHash(
        path=str(path),
        sha256=_hash_bytes(content),
        size=len(content),
    )


def _file_hash_to_dict(fh: FileHash) -> dict:
    return {"path": fh.path, "sha256": fh.sha256, "size": fh.size}


def _file_hash_from_dict(d: dict) -> FileHash:
    return FileHash(path=d["path"], sha256=d["sha256"], size=d["size"])


# ---------------------------------------------------------------------------
# File discovery helpers
# ---------------------------------------------------------------------------

# Match {% include "filename" %} or {% include 'filename' %}
_INCLUDE_RE = re.compile(r'\{%[-\s]*include\s+["\']([^"\']+)["\']')

# Match Typst image("path") calls
_IMAGE_RE = re.compile(r'image\(\s*"([^"]+)"')


def _discover_includes(template_path: Path) -> list[Path]:
    """Find files referenced by {% include %} in a .j2.typ template."""
    if not template_path.name.endswith(".j2.typ"):
        return []
    try:
        source = template_path.read_text()
    except OSError:
        return []

    template_dir = template_path.parent
    includes = []
    for match in _INCLUDE_RE.finditer(source):
        inc_path = template_dir / match.group(1)
        if inc_path.exists():
            includes.append(inc_path)
    return sorted(includes)


def _discover_assets(template_path: Path) -> list[Path]:
    """Find image files referenced in a template."""
    try:
        source = template_path.read_text()
    except OSError:
        return []

    template_dir = template_path.parent
    assets = []
    for match in _IMAGE_RE.finditer(source):
        image_path = match.group(1)
        if "{{" in image_path:
            continue  # Skip Jinja2 variables
        full_path = template_dir / image_path
        if full_path.exists():
            assets.append(full_path)
    return sorted(assets)


def _discover_fonts(font_paths: list[str] | None) -> list[Path]:
    """Find all font files in the given font directories."""
    if not font_paths:
        return []

    font_extensions = {".ttf", ".otf", ".ttc", ".woff", ".woff2"}
    fonts = []
    for font_dir in font_paths:
        p = Path(font_dir)
        if not p.is_dir():
            continue
        for f in sorted(p.iterdir()):
            if f.is_file() and f.suffix.lower() in font_extensions:
                fonts.append(f)
    return fonts


def _get_typst_version() -> str:
    """Best-effort detection of the Typst version."""
    # Try typst-py first
    try:
        import typst as _typst
        if hasattr(_typst, "__version__"):
            return str(_typst.__version__)
    except ImportError:
        pass

    # Try CLI
    import subprocess

    try:
        result = subprocess.run(
            ["typst", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip().split("\n")[0]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return "unknown"


def _get_backend_name() -> str:
    """Detect which backend would be used."""
    env_val = os.environ.get("TRUSTRENDER_BACKEND")
    if env_val:
        return env_val

    try:
        import typst as _typst  # noqa: F401
        return "typst-py"
    except ImportError:
        return "typst-cli"


# ---------------------------------------------------------------------------
# Fingerprint identity computation
# ---------------------------------------------------------------------------

def _compute_identity(fp_data: dict) -> str:
    """Compute the overall fingerprint hash from all fields."""
    canonical = json.dumps(
        fp_data, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode()
    return f"sha256:{hashlib.sha256(canonical).hexdigest()}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_fingerprint(
    template_path: str | os.PathLike,
    data: dict,
    *,
    font_paths: list[str] | None = None,
    zugferd_profile: str | None = None,
    provenance_enabled: bool = False,
    validate_enabled: bool = False,
) -> InputFingerprint:
    """Compute a cryptographic fingerprint of all render inputs.

    Args:
        template_path: Path to the template file.
        data: The data dict used for rendering.
        font_paths: Resolved font directories (after _build_font_paths).
        zugferd_profile: ZUGFeRD profile if applicable.
        provenance_enabled: Whether provenance embedding is enabled.
        validate_enabled: Whether contract validation is enabled.

    Returns:
        InputFingerprint with deterministic identity hash.
    """
    template_path = Path(template_path)

    # Hash the primary template
    template_hash = _hash_file(template_path)

    # Hash includes
    includes = _discover_includes(template_path)
    include_hashes = tuple(
        FileHash(
            path=str(inc.relative_to(template_path.parent)),
            sha256=_hash_bytes(inc.read_bytes()),
            size=inc.stat().st_size,
        )
        for inc in includes
    )

    # Hash assets
    assets = _discover_assets(template_path)
    asset_hashes = tuple(
        FileHash(
            path=str(asset.relative_to(template_path.parent)),
            sha256=_hash_bytes(asset.read_bytes()),
            size=asset.stat().st_size,
        )
        for asset in assets
    )

    # Hash fonts
    fonts = _discover_fonts(font_paths)
    font_hashes = tuple(
        FileHash(
            path=f.name,  # Just filename — font dirs may differ
            sha256=_hash_bytes(f.read_bytes()),
            size=f.stat().st_size,
        )
        for f in fonts
    )

    # Hash data
    data_hash = _hash_bytes(_canonical_json(data))

    # Config and environment
    backend = _get_backend_name()
    typst_version = _get_typst_version()
    created_at = datetime.now(timezone.utc).isoformat()

    # Compute identity hash from all content
    identity_data = {
        "template_hash": template_hash.sha256,
        "include_hashes": [h.sha256 for h in include_hashes],
        "asset_hashes": [h.sha256 for h in asset_hashes],
        "font_hashes": [h.sha256 for h in font_hashes],
        "data_hash": data_hash,
        "backend": backend,
        "zugferd_profile": zugferd_profile,
        "provenance_enabled": provenance_enabled,
        "validate_enabled": validate_enabled,
        "trustrender_version": __version__,
        "typst_version": typst_version,
    }
    fingerprint_hash = _compute_identity(identity_data)

    return InputFingerprint(
        template_hash=template_hash,
        include_hashes=include_hashes,
        asset_hashes=asset_hashes,
        font_hashes=font_hashes,
        data_hash=data_hash,
        backend=backend,
        zugferd_profile=zugferd_profile,
        provenance_enabled=provenance_enabled,
        validate_enabled=validate_enabled,
        trustrender_version=__version__,
        typst_version=typst_version,
        fingerprint=fingerprint_hash,
        created_at=created_at,
    )


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------

def _truncate(value: object, max_len: int = 200) -> str:
    """JSON-serialize and truncate a value for display."""
    try:
        s = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        s = str(value)
    if len(s) > max_len:
        return s[:max_len - 3] + "..."
    return s


def _diff_dicts(
    old: dict,
    new: dict,
    prefix: str = "",
) -> list[FieldChange]:
    """Recursively diff two dicts, producing FieldChange entries."""
    changes: list[FieldChange] = []

    all_keys = sorted(set(old.keys()) | set(new.keys()))
    for key in all_keys:
        path = f"{prefix}{key}" if not prefix else f"{prefix}.{key}"
        in_old = key in old
        in_new = key in new

        if in_old and not in_new:
            changes.append(FieldChange(
                path=path,
                change_type="removed",
                old_value=_truncate(old[key]),
                new_value=None,
            ))
        elif not in_old and in_new:
            changes.append(FieldChange(
                path=path,
                change_type="added",
                old_value=None,
                new_value=_truncate(new[key]),
            ))
        else:
            old_val = old[key]
            new_val = new[key]
            if isinstance(old_val, dict) and isinstance(new_val, dict):
                changes.extend(_diff_dicts(old_val, new_val, path))
            elif isinstance(old_val, list) and isinstance(new_val, list):
                changes.extend(_diff_lists(old_val, new_val, path))
            elif old_val != new_val:
                changes.append(FieldChange(
                    path=path,
                    change_type="modified",
                    old_value=_truncate(old_val),
                    new_value=_truncate(new_val),
                ))

    return changes


def _diff_lists(
    old: list,
    new: list,
    prefix: str,
) -> list[FieldChange]:
    """Diff two lists, producing FieldChange entries with index paths."""
    changes: list[FieldChange] = []

    max_len = max(len(old), len(new))
    for i in range(max_len):
        path = f"{prefix}[{i}]"
        if i >= len(old):
            changes.append(FieldChange(
                path=path,
                change_type="added",
                old_value=None,
                new_value=_truncate(new[i]),
            ))
        elif i >= len(new):
            changes.append(FieldChange(
                path=path,
                change_type="removed",
                old_value=_truncate(old[i]),
                new_value=None,
            ))
        else:
            old_val = old[i]
            new_val = new[i]
            if isinstance(old_val, dict) and isinstance(new_val, dict):
                changes.extend(_diff_dicts(old_val, new_val, path))
            elif isinstance(old_val, list) and isinstance(new_val, list):
                changes.extend(_diff_lists(old_val, new_val, path))
            elif old_val != new_val:
                changes.append(FieldChange(
                    path=path,
                    change_type="modified",
                    old_value=_truncate(old_val),
                    new_value=_truncate(new_val),
                ))

    return changes


def _diff_file_hashes(
    old: tuple[FileHash, ...],
    new: tuple[FileHash, ...],
) -> list[FileChange]:
    """Diff two sets of file hashes."""
    old_by_path = {h.path: h for h in old}
    new_by_path = {h.path: h for h in new}
    changes: list[FileChange] = []

    all_paths = sorted(set(old_by_path.keys()) | set(new_by_path.keys()))
    for path in all_paths:
        in_old = path in old_by_path
        in_new = path in new_by_path
        if in_old and not in_new:
            changes.append(FileChange(
                path=path, change_type="removed",
                old_hash=old_by_path[path].sha256, new_hash=None,
            ))
        elif not in_old and in_new:
            changes.append(FileChange(
                path=path, change_type="added",
                old_hash=None, new_hash=new_by_path[path].sha256,
            ))
        elif old_by_path[path].sha256 != new_by_path[path].sha256:
            changes.append(FileChange(
                path=path, change_type="modified",
                old_hash=old_by_path[path].sha256,
                new_hash=new_by_path[path].sha256,
            ))

    return changes


def compare(
    baseline: InputFingerprint,
    current: InputFingerprint,
    baseline_data: dict | None = None,
    current_data: dict | None = None,
) -> ChangeSet:
    """Compare two fingerprints and produce a detailed ChangeSet.

    Args:
        baseline: The baseline fingerprint to compare against.
        current: The current fingerprint.
        baseline_data: Original data dict (for field-level diff). Optional.
        current_data: Current data dict (for field-level diff). Optional.

    Returns:
        ChangeSet describing all differences. Empty if identical.
    """
    cs = ChangeSet(
        baseline_fingerprint=baseline.fingerprint,
        current_fingerprint=current.fingerprint,
    )

    # Template changes
    if baseline.template_hash.sha256 != current.template_hash.sha256:
        cs.template_changes.append(FileChange(
            path=current.template_hash.path,
            change_type="modified",
            old_hash=baseline.template_hash.sha256,
            new_hash=current.template_hash.sha256,
        ))

    # Include changes
    cs.template_changes.extend(
        _diff_file_hashes(baseline.include_hashes, current.include_hashes)
    )

    # Asset changes
    cs.asset_changes = _diff_file_hashes(baseline.asset_hashes, current.asset_hashes)

    # Font changes
    cs.font_changes = _diff_file_hashes(baseline.font_hashes, current.font_hashes)

    # Data changes (field-level if dicts provided, hash-level otherwise)
    if baseline.data_hash != current.data_hash:
        if baseline_data is not None and current_data is not None:
            cs.data_changes = _diff_dicts(baseline_data, current_data)
        else:
            # Can only report hash changed, not which fields
            cs.data_changes = [FieldChange(
                path="(data)",
                change_type="modified",
                old_value=baseline.data_hash,
                new_value=current.data_hash,
            )]

    # Config changes
    config_fields = [
        ("backend", baseline.backend, current.backend),
        ("zugferd_profile", baseline.zugferd_profile, current.zugferd_profile),
        ("provenance_enabled", baseline.provenance_enabled, current.provenance_enabled),
        ("validate_enabled", baseline.validate_enabled, current.validate_enabled),
    ]
    for key, old_val, new_val in config_fields:
        if old_val != new_val:
            cs.config_changes.append(ConfigChange(
                key=key, old_value=_truncate(old_val), new_value=_truncate(new_val),
            ))

    # Environment changes
    env_fields = [
        ("trustrender_version", baseline.trustrender_version, current.trustrender_version),
        ("typst_version", baseline.typst_version, current.typst_version),
    ]
    for key, old_val, new_val in env_fields:
        if old_val != new_val:
            cs.environment_changes.append(ConfigChange(
                key=key, old_value=old_val, new_value=new_val,
            ))

    return cs
