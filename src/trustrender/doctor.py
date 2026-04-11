"""Environment diagnostics for TrustRender."""

from __future__ import annotations

import importlib.metadata
import os
import subprocess
import sys
import time
from pathlib import Path

# Status constants
OK = "ok"
WARN = "warn"
FAIL = "FAIL"
INFO = "info"


def _label(status: str, msg: str) -> str:
    return f"  [{status:>4s}]  {msg}"


def check_python_version() -> tuple[str, str]:
    v = sys.version_info
    version_str = f"{v.major}.{v.minor}.{v.micro}"
    if (v.major, v.minor) >= (3, 11):
        return OK, f"Python {version_str} (>=3.11 required)"
    return FAIL, f"Python {version_str} — requires >=3.11"


def check_trustrender_import() -> tuple[str, str]:
    try:
        import trustrender

        return OK, f"trustrender {trustrender.__version__} importable"
    except ImportError as exc:
        return FAIL, f"Cannot import trustrender: {exc}"


def check_typst_py() -> tuple[str, str]:
    """Check typst Python binding. Warn if missing (CLI backend still works)."""
    try:
        version = importlib.metadata.version("typst")
        return OK, f"typst-py {version} (Python binding)"
    except importlib.metadata.PackageNotFoundError:
        return WARN, "typst-py not installed (library can still use typst-cli backend)"


def check_typst_cli() -> tuple[str, str]:
    """Check typst CLI binary. Warn if missing (typst-py backend still works)."""
    try:
        result = subprocess.run(
            ["typst", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            version = result.stdout.strip().split("\n")[0]
            return OK, f"typst CLI: {version}"
        return WARN, "typst CLI found but returned an error"
    except FileNotFoundError:
        return WARN, (
            "typst CLI not found on PATH\n"
            "         Install: brew install typst (macOS) or cargo install typst-cli\n"
            "         See: https://github.com/typst/typst\n"
            "         Note: server mode requires typst CLI for timeout safety"
        )
    except subprocess.TimeoutExpired:
        return WARN, "typst CLI found but timed out"


def check_backends(typst_py_status: str, typst_cli_status: str) -> tuple[str, str]:
    """Check that at least one backend is usable. Report capability."""
    py_ok = typst_py_status == OK
    cli_ok = typst_cli_status == OK

    if py_ok and cli_ok:
        return OK, "Both backends available (library + server)"
    if py_ok and not cli_ok:
        return WARN, (
            "Only typst-py backend available\n"
            "         Library rendering works, but server mode requires typst CLI"
        )
    if cli_ok and not py_ok:
        return OK, "Only typst-cli backend available (library + server both work)"
    return FAIL, (
        "No backend available — rendering is impossible\n"
        "         Install typst-py: pip install 'typst>=0.14'\n"
        "         Install typst CLI: brew install typst (macOS) or cargo install typst-cli"
    )


def check_fonts_dir() -> tuple[str, str]:
    from trustrender import bundled_font_dir

    fonts = bundled_font_dir()
    if fonts is None:
        return WARN, "Bundled font directory not found (system fonts will be used)"
    font_files = list(fonts.glob("**/*.ttf")) + list(fonts.glob("**/*.otf"))
    return OK, f"Bundled fonts: {fonts} ({len(font_files)} files)"


def check_template_fonts(templates_dir: Path | None = None) -> tuple[str, str]:
    """Font inventory — check that fonts declared in templates are available.

    Uses the same font-declaration parser as preflight (readiness module) to
    ensure the Doctor and the Preflight engine see the exact same requirements.
    Handles both single fonts (``font: "Inter"``) and font stacks
    (``font: ("Inter", "Noto Sans")``).
    """
    import re

    from trustrender import bundled_font_dir
    from trustrender.readiness import _parse_declared_fonts

    fonts_dir = bundled_font_dir()

    # Collect available font family names from all configured font paths
    available: dict[str, str] = {}  # lowercase name → source description
    if fonts_dir is not None:
        for ext in ("*.ttf", "*.otf"):
            for f in fonts_dir.glob(f"**/{ext}"):
                name = re.split(r"[-_]", f.stem)[0].lower()
                if name and name not in available:
                    available[name] = f"bundled: {fonts_dir}"

    env_path = os.environ.get("TRUSTRENDER_FONT_PATH")
    env_families: set[str] = set()
    if env_path and Path(env_path).is_dir():
        for ext in ("*.ttf", "*.otf"):
            for f in Path(env_path).glob(f"**/{ext}"):
                name = re.split(r"[-_]", f.stem)[0].lower()
                if name:
                    env_families.add(name)
                    if name not in available:
                        available[name] = f"TRUSTRENDER_FONT_PATH: {env_path}"

    # Find templates
    if templates_dir is None:
        repo_root = _find_repo_root()
        if repo_root is None:
            return WARN, "Font check skipped — examples/ directory not found"
        templates_dir = repo_root / "examples"

    # Parse font declarations from templates (single fonts + font stacks)
    declared: set[str] = set()
    missing: list[tuple[str, str]] = []  # (template, font_name)

    for template in templates_dir.glob("**/*.typ"):
        if template.name.startswith("_trustrender_"):
            continue
        try:
            content = template.read_text()
        except Exception:
            continue
        for stack in _parse_declared_fonts(content):
            for font_name in stack:
                declared.add(font_name)
                if font_name.lower() not in available:
                    missing.append((template.name, font_name))

    if not declared:
        return OK, "Font inventory: no font declarations found in templates"

    # Build multi-line inventory
    declared_str = ", ".join(sorted(declared))
    found_names = sorted(n for n in declared if n.lower() in available)
    missing_names = sorted({f for _, f in missing})

    if missing_names:
        lines = [
            "Font inventory:",
            f"         Declared: {declared_str}",
        ]
        if found_names:
            found_detail = ", ".join(
                f"{n} ({available[n.lower()]})" for n in found_names
            )
            lines.append(f"         Found:    {found_detail}")
        else:
            lines.append("         Found:    (none in configured paths)")
        lines.append(f"         Missing:  {', '.join(missing_names)}")
        if env_families:
            lines.append(
                f"         Env path: {env_path} ({len(env_families)} "
                f"{'family' if len(env_families) == 1 else 'families'}: "
                f"{', '.join(sorted(env_families))})"
            )
        # Actionable fix commands
        if "Inter" in missing_names:
            lines.append(
                "         Fix:      download Inter from https://fonts.google.com/specimen/Inter"
            )
        target = env_path or (str(fonts_dir) if fonts_dir else None)
        if target:
            lines.append(f"         Path:     install missing fonts to {target}")
        else:
            lines.append(
                "         Tip:      set TRUSTRENDER_FONT_PATH to a directory with your fonts"
            )
        return WARN, "\n".join(lines)

    found_detail = ", ".join(
        f"{n} ({available[n.lower()]})" for n in found_names
    )
    result = f"Font inventory: {declared_str} — all found ({found_detail})"
    if env_families:
        result += (
            f"\n         Env path: {env_path} ({len(env_families)} "
            f"{'family' if len(env_families) == 1 else 'families'}: "
            f"{', '.join(sorted(env_families))})"
        )
    return OK, result


def check_env_backend() -> tuple[str, str]:
    val = os.environ.get("TRUSTRENDER_BACKEND")
    if val is None:
        return INFO, "TRUSTRENDER_BACKEND not set (auto-detect)"
    if val in ("typst-py", "typst-cli"):
        return INFO, f"TRUSTRENDER_BACKEND={val}"
    return WARN, f"TRUSTRENDER_BACKEND={val!r} (invalid — use 'typst-py' or 'typst-cli')"


def check_env_font_path() -> tuple[str, str]:
    val = os.environ.get("TRUSTRENDER_FONT_PATH")
    if val is None:
        return INFO, "TRUSTRENDER_FONT_PATH not set (using bundled)"
    if Path(val).is_dir():
        return INFO, f"TRUSTRENDER_FONT_PATH={val}"
    return WARN, f"TRUSTRENDER_FONT_PATH={val} (directory does not exist)"


def _find_repo_root() -> Path | None:
    """Walk up from the trustrender package to find the repo root with examples/."""
    try:
        import trustrender

        pkg_path = Path(trustrender.__file__).resolve().parent
        # src-layout: src/trustrender/__init__.py -> repo_root is ../../
        candidate = pkg_path.parent.parent
        if (candidate / "examples").is_dir():
            return candidate
    except Exception:
        pass

    # Fallback: check cwd
    cwd = Path.cwd()
    if (cwd / "examples").is_dir():
        return cwd

    return None


def check_smoke_render() -> tuple[str, str]:
    """Render the example invoice and verify output."""
    repo_root = _find_repo_root()
    if repo_root is None:
        return WARN, "Smoke render skipped — examples/ directory not found"

    template = repo_root / "examples" / "invoice.j2.typ"
    data = repo_root / "examples" / "invoice_data.json"

    if not template.exists() or not data.exists():
        return WARN, "Smoke render skipped — example invoice files not found"

    try:
        from trustrender import render

        start = time.monotonic()
        pdf_bytes = render(str(template), str(data))
        elapsed = time.monotonic() - start

        if not pdf_bytes[:5] == b"%PDF-":
            return FAIL, "Smoke render produced output but it is not a valid PDF"

        size_kb = len(pdf_bytes) / 1024
        return OK, f"Smoke render: {size_kb:.0f} KB in {elapsed:.2f}s"
    except Exception as exc:
        return FAIL, f"Smoke render failed: {exc}"


def check_smoke_server() -> tuple[str, str]:
    """Check server /health endpoint in-process (no network port)."""
    repo_root = _find_repo_root()
    if repo_root is None:
        return WARN, "Server health skipped — examples/ directory not found"

    examples_dir = repo_root / "examples"
    if not examples_dir.is_dir():
        return WARN, "Server health skipped — examples/ directory not found"

    try:
        from starlette.testclient import TestClient

        from trustrender.server import create_app

        app = create_app(str(examples_dir))
        client = TestClient(app)
        resp = client.get("/health")

        if resp.status_code == 200 and resp.json().get("status") == "ok":
            return OK, "Server /health: ok (in-process, no port)"
        return FAIL, f"Server /health returned: {resp.status_code} {resp.text}"
    except ImportError:
        return WARN, "Server health skipped — httpx/starlette testclient not available"
    except Exception as exc:
        return FAIL, f"Server health check failed: {exc}"


def run_doctor(smoke: bool = False) -> int:
    """Run all diagnostic checks. Returns 0 if all pass, 1 if any fail."""
    print("\ntrustrender doctor\n")

    checks: list[tuple[str, str]] = []

    # Core checks
    checks.append(check_python_version())
    checks.append(check_trustrender_import())

    typst_py_result = check_typst_py()
    checks.append(typst_py_result)

    typst_cli_result = check_typst_cli()
    checks.append(typst_cli_result)

    checks.append(check_backends(typst_py_result[0], typst_cli_result[0]))
    checks.append(check_fonts_dir())
    checks.append(check_template_fonts())

    # Environment
    checks.append(check_env_backend())
    checks.append(check_env_font_path())

    # Smoke tests (optional)
    if smoke:
        checks.append(check_smoke_render())
        checks.append(check_smoke_server())

    # Print results
    fails = 0
    warns = 0
    for status, msg in checks:
        print(_label(status, msg))
        if status == FAIL:
            fails += 1
        elif status == WARN:
            warns += 1

    print()
    if fails:
        print(f"  {fails} check(s) failed, {warns} warning(s).\n")
        return 1
    elif warns:
        print(f"  All checks passed with {warns} warning(s).\n")
        return 0
    else:
        print("  All checks passed.\n")
        return 0
