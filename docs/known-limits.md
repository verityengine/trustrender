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
- Invoice type code 380 (standard VAT invoice)
- SEPA credit transfer and direct debit payment means

Not supported (fails loudly at validation time):
- Credit notes (type 381)
- Reverse charge invoices
- Intra-community supply
- Non-EUR currencies
- Non-DE countries
- Allowances, charges, or discounts (hardcoded to zero in XML; rejected at validation if present in data)
- Extended/Basic/Minimum profiles

### XRechnung not yet validated

Code paths exist for XRechnung (guideline ID, Leitweg-ID, BR-DE-5 contact requirements). However, the generated XML fails Schematron validation against the factur-x Schematron rules because the XRechnung guideline ID is not in the allowed set for the EN 16931 Schematron. Proper XRechnung validation requires KOSIT's XRechnung-specific Schematron rules, which are not currently integrated.

XRechnung is not listed as a supported profile. The `zugferd="xrechnung"` code path exists but should not be used in production until Schematron validation passes.

### Mustang validation is manual

One-time manual validation against the Mustang reference validator has passed for the EN 16931 profile (see `docs/zugferd-prototype.md`). This is not automated in CI. `preflight()` runs XSD validation when `facturx` is installed, but Schematron and Mustang validation are test-suite-only.

### XSD/Schematron validation is not in the render pipeline

The `render()` function validates invoice data fields (required fields, currency, country, tax rates) but does not run XSD or Schematron validation on the generated XML. `preflight()` runs XSD validation when the `facturx` library is available. Schematron validation runs only in the test suite.

### Font fallback is silent

Typst silently falls back to a default font when a requested font family is unavailable. No error is raised. The PDF is valid but may use the wrong font.

Implications:
- A typo in a font name produces a valid PDF with the wrong font and zero errors
- `ErrorCode.MISSING_FONT` only fires for explicit Typst font errors (e.g., corrupted font files), which are rare
- Missing-font detection is inherently incomplete because silent fallback usually wins
- Currently observed default fallback: Libertinus (not guaranteed by upstream Typst)

Mitigation: Use bundled fonts (Inter) or explicitly supplied fonts via `font_paths`. Do not rely on system font availability.

### Template escaping has boundaries

Auto-escaping covers text content contexts. It handles: `\`, `$`, `#`, `@`, `{`, `}`, `[`, `]`, `<`, `` ` ``, `~`.

Not auto-escaped:
- Typst code mode contexts (content inside `#` expressions)
- Typst math mode contexts (content inside `$` delimiters)
- Values passed through the `typst_markup` filter (intentionally bypasses escaping)
- The `color` parameter of the `typst_color` filter (template-author-controlled)

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

### No rate limiting

Formforge's HTTP server has no built-in rate limiting, IP throttling, or concurrent request limits. It has:
- 1MB request body size limit
- Configurable render timeout (default 30s, subprocess kill)
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

### Silent font fallback means wrong output, not errors

If a template requests a font that is not available, Typst will silently use a fallback font. The render succeeds. The PDF is valid. The font is wrong. No error code is returned.

This means: font misconfiguration in production will produce subtly wrong PDFs with no alerting. The only defense is to use bundled or explicitly supplied fonts and verify output visually during deployment.

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
