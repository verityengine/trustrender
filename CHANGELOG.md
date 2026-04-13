# Changelog

## 0.3.1

- Add `from_stripe()` adapter for raw Stripe Invoice API payloads
- Add `--source stripe` flag to `trustrender validate`
- Converts Stripe-specific formats: cents to dollars, Unix timestamps to dates, nested `lines.data[]` to flat items, `price.unit_amount` extraction
- Stripe example: `examples/validate_stripe.py`

## 0.3.0

Validation-first repositioning. TrustRender is now usable as a lightweight invoice validation library without rendering dependencies.

### New

- **`validate_invoice()` public API** — validate and normalize messy invoice data in one call. Returns structured result with canonical payload, errors, warnings, normalizations, and optional ZUGFeRD readiness check. No rendering deps required.
- **`trustrender validate` CLI command** — validate invoice JSON from the command line. Human-readable output with plain-language error messages. Exit codes: 0=pass, 1=blocked, 2=warnings. JSON output via `--format json`. ZUGFeRD checks via `--zugferd`.
- **Interop example** (`examples/validate_before_embed.py`) — demonstrates TrustRender validate → drafthorse/factur-x handoff.

### Changed

- **Rendering dependencies are now optional.** `pip install trustrender` installs only `drafthorse` (~2MB). Typst, Jinja2, Starlette, uvicorn, and pypdf moved to optional extras:
  - `pip install trustrender[render]` — PDF rendering via Typst
  - `pip install trustrender[serve]` — HTTP server
  - `pip install trustrender[zugferd]` — XSD/Schematron validation
  - `pip install trustrender[all]` — everything
- **CLI reordered.** `validate` and `ingest` are now the first commands in `--help`. Rendering commands note they require `trustrender[render]`.
- **Package description** updated to: "Validate and normalize messy invoice data for Factur-X/ZUGFeRD compliance."
- Calling `render()` or `audit()` without render extras installed now raises a clear error: "Install with: pip install trustrender[render]".

### Unchanged

- All rendering behavior is identical when `trustrender[render]` is installed.
- All 161 backend tests pass. All 61 browser tests pass.
- Invoice normalization pipeline (90+ aliases, type coercion, arithmetic checks) unchanged.
- ZUGFeRD EN 16931 support (DE/EUR/standard VAT) unchanged.

## 0.2.0

Initial PyPI release. Invoice ingest pipeline, deterministic Typst rendering, ZUGFeRD EN 16931 support, preflight checks, provenance embedding, HTTP server.
