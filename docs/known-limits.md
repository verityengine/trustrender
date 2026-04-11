# Formforge Known Limitations

Updated: 2026-04-11 (post trust-gap closure: letter/report presets, text anomaly detection, strict preflight)

Honest documentation of what Formforge does not do, does partially, or does with caveats.

---

## For Evaluators

### ZUGFeRD scope is narrow

Supported:
- EN 16931 profile only
- German domestic B2B invoices
- EUR currency only
- Single or mixed VAT rates per invoice (e.g., 7% + 19%)
- Invoice type codes 380 (standard VAT invoice) and 381 (credit note)
- Credit notes with referenced_invoice (BT-25)
- SEPA credit transfer and direct debit payment means

Not supported (fails loudly at validation time):
- Reverse charge invoices
- Intra-community supply
- Non-EUR currencies
- Non-DE countries
- Allowances, charges, or discounts (hardcoded to zero in XML; rejected at validation if present in data)
- Extended/Basic/Minimum profiles

### Mustang validation is manual

One-time manual validation against the Mustang reference validator has passed for the EN 16931 profile (see `docs/zugferd-prototype.md`). This is not automated in CI but is available locally via `make mustang-validate` (requires Java). `preflight()` and `render()` both run XSD validation when `facturx` is installed. Schematron and Mustang validation are not in the render pipeline.

### Schematron validation is not in the render pipeline

XSD validation runs in both `render()` (as a guard rail after XML generation, before PDF embedding — raises `ZUGFERD_ERROR` on failure) and `preflight()` (when the `facturx` library is available). Schematron validation runs only in the test suite and is not enforced at render time.

### Font fallback is silent — detected in preflight

Typst silently falls back to a default font when a requested font family is unavailable. No error is raised at render time. The PDF is valid but visually different.

This has been measured (see `benchmarks/font_swap_results.md`):
- Render succeeds silently with wrong font
- Page count stays the same
- File size stays the same (0% difference)
- Output bytes are different (visual change)

**Pre-render detection (preflight):** `preflight()` parses `#set text(font: "...")` declarations from template source and verifies each declared font against configured font paths (bundled + explicit). For bundled templates expecting bundled fonts (Inter), a missing font is an **error** that blocks readiness. For custom templates, a missing font is a **warning** (it may be available as a system font). `strict=True` promotes all missing-font warnings to errors.

**Post-render detection (drift):** Drift detection extracts embedded font names from the PDF (via pypdf) and compares against the baseline. When the font set changes, a **warning** is produced (e.g. "Embedded fonts changed: removed Inter-Regular; added Libertinus-Regular").

Limitations:
- Preflight verifies against configured font paths only — system fonts cannot be reliably enumerated, so a font not in configured paths gets a warning (not an error) unless it's a bundled font on a bundled template
- Preflight is a gate for callers who use it — the render path itself does not block on missing fonts
- Drift detection is baseline-dependent: only works after a known-good baseline is saved
- `ErrorCode.MISSING_FONT` only fires for explicit Typst font errors (e.g., corrupted font files), which are rare
- Currently observed default fallback: Libertinus (not guaranteed by upstream Typst)
- Not a visual diff — only checks font names, not rendering fidelity

Mitigation: Use `preflight()` or `formforge preflight` before rendering to catch missing fonts. Use bundled fonts (Inter) or explicitly supplied fonts via `font_paths`. Run `formforge doctor` for a full font inventory with fix commands. Save baselines in CI to catch font drift across environments.

### Template escaping has boundaries

Auto-escaping covers text content contexts. It handles: `\`, `$`, `#`, `@`, `{`, `}`, `[`, `]`, `<`, `` ` ``, `~`, plus `=`, `-`, `+`, `/` at line-start positions (prevents heading/list/description-list injection from user data).

Not auto-escaped:
- Typst code mode contexts (content inside `#` expressions)
- Typst math mode contexts (content inside `$` delimiters)
- Values passed through the `typst_markup` filter (intentionally bypasses escaping)
- The `color` parameter of the `typst_color` filter (template-author-controlled)
- `_` and `*` (word-boundary emphasis — escaping everywhere would degrade `snake_case` readability)

If user data must appear in code or math mode, template authors must escape it manually.

### Contract validation has caveats

What it does:
- Infers structural data contracts from Jinja2 template AST
- Detects: required fields, optional fields, scalar vs list vs object types, nested hierarchies
- Validates data against inferred contract before rendering

What it does not:
- Support Jinja2 macros
- Narrow types beyond structural (no int/str/float distinction)
- Guarantee correctness of `required` vs `optional` beyond direct `{% if field %}` guards

Note: Contract inference follows `{% include %}` directives recursively for static includes. Dynamic includes (`{% include some_var %}`) are marked unresolved and the contract is flagged as partial.

### Semantic currency parsing scope

The semantic validator parses currency amounts by stripping `€`, `$`, `£`, `¥`, whitespace, and commas, then calling `float()`. Other currency symbols are not supported:

Not parsed: `₹` (Indian Rupee), `R$` (Brazilian Real), `kr` (Swedish Krona), `zł` (Polish Złoty), `₱` (Philippine Peso), `₽` (Russian Ruble), and others.

When an amount uses an unsupported symbol, `_try_parse_number` returns `None`. This means:
- Arithmetic consistency checks silently skip (subtotal unparseable)
- Numeric coercion checks fire warnings (expected numeric, got string)
- No crash, no error — just reduced semantic coverage

### European number format not supported

Numbers formatted as `1.234,56` (period as thousands separator, comma as decimal) are not parseable by the semantic validator. The comma is stripped as a thousands separator, leaving `1.234.56` which fails `float()`.

This affects: German, French, Italian, Spanish, and most European number conventions. Workaround: pass numeric amounts as integers/floats or use US-style formatting for semantic validation.

### Float precision in semantic checks

Semantic arithmetic checks use Python `float` (IEEE 754 double precision). Numbers beyond 2^53 lose integer precision silently. This affects only semantic comparisons — rendering is unaffected because amounts are strings in templates.

Arithmetic tolerance is `> 0.01` (strictly greater than one cent). Due to IEEE 754 representation, differences at exactly $0.01 may fire false warnings (e.g., `abs(30.0 - 30.01) = 0.010000000000001563`).

### Non-finite values rejected

As of 2026-04-12, `_try_parse_number` rejects Infinity, -Infinity, and NaN via `math.isfinite()`. These are mathematically valid floats but not valid business amounts.

### Performance numbers are from manual runs

Published benchmarks (56ms latency, 53.8 RPS, 500 soak renders) are from a single manual run on Apple Silicon macOS. They are not automated, tracked, or reproduced in CI. The soak test harness exists and results are committed to `benchmarks/soak_results.md`.

WeasyPrint comparison (2.3x faster) was measured on the same hardware for a simple invoice template only.

---

## For Operators

### No rate limiting (but has backpressure)

Formforge's HTTP server has no built-in rate limiting or IP throttling. It does have:
- Render concurrency limit: ``--max-concurrent`` (default 8), returns 503 when at capacity
- 10MB request body size limit (configurable via ``--max-body-size``)
- Configurable render timeout: ``--render-timeout`` (default 30s, subprocess kill)
- Request validation (required fields, types, path traversal)

For production deployment, use a reverse proxy (nginx, AWS WAF, Cloudflare) for rate limiting.

### Temp file policy

On success: temp `.typ` file deleted immediately (unless `debug=True`).
On timeout (production): temp file deleted, `source_path` cleared from error.
On timeout (debug): temp file preserved for inspection.
On compile error: temp file preserved for inspection.
On unexpected error: temp file deleted in finally block.

Temp files are named `_formforge_<random>.typ` (unpredictable via `tempfile.mkstemp`) and placed in the template's directory.

Failed renders can accumulate temp files over time. No automatic cleanup facility exists. Operators should monitor and clean the template directory if running many renders that fail at the compile stage.

### Font fallback

Typst can silently substitute missing fonts. Formforge detects this at two levels:

1. **Preflight** (pre-render): parses font declarations from template source, verifies against configured font paths. Bundled templates with missing bundled fonts produce errors; custom templates produce warnings. This is a gate for callers who use `preflight()` — the render path itself is unchanged.
2. **Drift detection** (post-render): records embedded-font drift in baselines and raises a warning when the font set changes.

Neither is a full visual-diff guarantee. For deterministic output, rely on bundled or explicitly supplied fonts. Run `formforge doctor` for a full font inventory with actionable fix commands.

### typst-py backend cannot kill timeouts

The typst-py backend (in-process Python binding) accepts a `timeout` parameter but cannot actually interrupt execution. If a template triggers an infinite loop or very slow render, typst-py will block until completion.

The server always uses the typst-cli backend (subprocess) for this reason. If you use the library API directly, be aware that typst-py timeout is best-effort.

### Docker needs locale configuration

The Dockerfile uses `python:3.12-slim` which defaults to C/POSIX locale. For non-Latin Unicode rendering, explicit locale configuration (`ENV LANG=en_US.UTF-8`) should be added. This is not currently set.

Docker Unicode rendering has not been tested. The claim "Docker output matches local" is stated but not automated.

### Server uses CLI backend exclusively

The HTTP server always uses `TypstCliBackend` (subprocess) regardless of the `FORMFORGE_BACKEND` environment variable. This is intentional: subprocess isolation enables real timeout kill and prevents a runaway render from affecting other requests.

Operators cannot use typst-py with the server. This is the correct behavior.

---

## For Template Authors

### Code mode and math mode are not auto-escaped

Formforge auto-escapes user data for text content contexts. But if you place user data inside Typst code expressions (`#let x = {{ value }}`) or math mode (`$ {{ value }} $`), the escaping does not apply to those contexts.

Safe:
```
{{ company_name }}           // text context, auto-escaped
{{ amount | typst_money }}   // filter returns pre-escaped markup
```

Potentially unsafe (if value contains Typst syntax):
```
#let x = {{ user_input }}    // code context, not escaped for code mode
$ {{ formula }} $             // math context, not escaped for math mode
```

### typst_markup filter bypasses escaping

The `typst_markup` filter marks content as safe Typst markup, bypassing auto-escaping. Use it only for values you control (precomputed markup, trusted strings). Never pass raw user input through `typst_markup`.

### typst_color filter color parameter

The `color` parameter in `{{ value | typst_color("#27ae60") }}` is not escaped or validated. It must be a hex color code or valid Typst color name. Do not pass user data as the color parameter.

### Text anomaly detection is narrow by design

Semantic validation detects control characters (U+0000-U+001F except tab, newline, carriage return) and zero-width characters (U+200B, U+200C, U+200D, U+FEFF, U+2060) in hinted text fields. Warnings name the exact character: null byte, form feed, zero-width space, BOM, word joiner.

What it does not detect:
- Garbage strings, repeated characters, or suspicious patterns — too many false positives
- Unicode normalization issues (NFC vs NFD) — data pipeline concern
- Absurd field length — layout overflow is the template's responsibility
- Characters in unhinted fields — only fields listed in `text_check_fields` are scanned

### Contract inference is heuristic

The `required` vs `optional` distinction is based on whether a field appears inside a direct `{% if field %}` guard. More complex conditional patterns (nested ifs, boolean combinations, filter-based checks) may not be detected correctly.

If contract accuracy matters for your use case, review the inferred contract with `formforge check <template>` and validate against your data schema manually.

### Dynamic includes produce partial contracts

Static includes (`{% include "fragment.j2.typ" %}`) are followed recursively — fields from included fragments are merged into the contract. But dynamic includes (`{% include some_var %}`) cannot be resolved statically.

When a contract is partial, `preflight()` warns by default. Use `preflight(strict=True)` or `formforge preflight --strict` to promote partial-contract warnings to errors — readiness fails if the contract is provably incomplete.
