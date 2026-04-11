# Formforge

Generate structured business PDFs from data + templates. No browser, no Chromium.

Formforge renders invoices, statements, receipts, and similar structured documents using [Typst](https://typst.app/) as the layout engine and Jinja2 for data binding. It ships as a Python library, CLI, and HTTP server.

## Non-goals

Formforge is not:

- arbitrary HTML-to-PDF conversion
- a browser or headless renderer
- a visual/WYSIWYG editor
- DOCX, PPTX, or multi-format output
- a general document platform

It does one thing: structured business PDFs from code.

## Install

### Standard install (recommended)

```
git clone https://github.com/verityengine/formforge.git
cd formforge
pip install .
```

This is the most reliable local path today.

### Development install

```
pip install -e ".[dev]"
```

Editable install is intended for development workflows. Use the standard install above if you just want to run Formforge.

### Requirements

- Python 3.11+
- Python package dependencies (`typst`, `jinja2`, `starlette`, `uvicorn`) are installed automatically by `pip install .`
- **Typst CLI binary** is a separate install, required for the `typst-cli` backend (and always used by the server). The binary name on PATH must be `typst`. Install via:
  - macOS: `brew install typst`
  - Cargo: `cargo install --git https://github.com/typst/typst --locked typst-cli`
  - Or download from [typst.app](https://typst.app/)

The `typst` Python package (used by the `typst-py` backend) is a pip dependency and installed automatically. The Typst CLI binary is a separate system-level install — it is always required by server mode and recommended for all usage.

### Verify your install

```
formforge doctor
```

This checks Python version, package imports, Typst backends, fonts, and environment variables. Run it first if anything seems broken.

With a render smoke test:

```
formforge doctor --smoke
```

## Quick start

**Python API:**

```python
from formforge import render

pdf_bytes = render(
    "examples/invoice.j2.typ",
    "examples/invoice_data.json",
    output="invoice.pdf",
)
print(f"Rendered {len(pdf_bytes)} bytes")
```

**CLI:**

```
formforge render examples/invoice.j2.typ examples/invoice_data.json -o invoice.pdf
```

Both produce `invoice.pdf` from the bundled example template and data. Template and data paths are resolved relative to the current working directory.

## CLI usage

```
formforge render <template> <data.json> -o <output.pdf> [--debug] [--no-validate] [--zugferd en16931] [--font-path <dir>]
formforge check <template> [--data <data.json>]
formforge serve --templates <dir> [--host 127.0.0.1] [--port 8190] [--debug] [--font-path <dir>]
formforge doctor [--smoke]
```

Common examples:

```
# Render a single PDF
formforge render templates/invoice.j2.typ data.json -o out.pdf

# Render with custom fonts
formforge render templates/invoice.j2.typ data.json -o out.pdf --font-path ./my-fonts

# Start the HTTP server
formforge serve --templates ./templates --port 8190

# Start with debug mode (preserves intermediate files)
formforge serve --templates ./templates --debug
```

Full flag reference: `formforge render --help` / `formforge serve --help`.

## Data validation

For Jinja2 Typst templates, Formforge validates data before rendering by default. Bad payloads are rejected with specific field-level errors before any Typst compilation starts.

### Structural validation (default)

Every `render()` call on a `.j2.typ` template infers a minimum data contract from the Jinja2 AST and validates caller data against it. This catches:

- missing required fields
- null values on required fields
- wrong structural types (passing a string where an object is expected, a dict where a list is expected)
- requirements from `{% include %}` fragments (followed recursively with scope isolation)

Bad data raises `FormforgeError(code=DATA_CONTRACT)` with paths pointing into the caller's JSON:

```python
render("invoice.j2.typ", {"invoice_number": "X"})
```

```
FormforgeError: Data validation failed: 11 field errors in invoice.j2.typ
  sender: missing required field (expected: object)
  recipient: missing required field (expected: object)
  items: missing required field (expected: list[object])
  invoice_date: missing required field
  ...
```

Raw `.typ` files are unaffected — they have no Jinja2 AST to infer a contract from.

To skip structural validation explicitly:

```python
render("invoice.j2.typ", data, validate=False)
```

```
formforge render invoice.j2.typ data.json -o out.pdf --no-validate
```

`validate=False` is an escape hatch for callers who know their data shape and want to skip the check, not the normal path.

### Semantic validation (opt-in, hint-driven)

Beyond structure, Formforge can check business-data correctness when the caller configures semantic hints. Semantic checks warn but do not block rendering.

What semantic validation catches:

- **Arithmetic mismatches**: line item totals that don't sum to the stated subtotal
- **Balance reconciliation**: aging bucket totals that don't sum to the closing balance (statements)
- **Unparseable dates**: strings in date fields that don't match any common format
- **Non-numeric values**: currency fields containing non-parseable text
- **Empty required fields**: business-critical fields that are blank strings or None

```python
from formforge.semantic import validate_semantics, STATEMENT_HINTS

report = validate_semantics(statement_data, STATEMENT_HINTS)
# Issues found:
#   [warning] arithmetic: aging.total — sum of aging buckets = 18267.50, but aging.total = 999999.00
```

Semantic hints are not inferred. The caller declares what to check. Presets exist for common document types:

| Preset | Template types | Checks |
|--------|---------------|--------|
| `INVOICE_HINTS` | invoices, e-invoices | line item sum, dates, numerics, invoice number, text anomalies |
| `RECEIPT_HINTS` | receipts | item amounts, subtotal, dates, numerics, text anomalies |
| `STATEMENT_HINTS` | account statements | balance reconciliation, aging totals, dates, numerics, text anomalies |
| `LETTER_HINTS` | business letters | date, sender/recipient names, subject, closing, text anomalies |
| `REPORT_HINTS` | reports | date, title, company name, executive summary, spend numerics, text anomalies |

The CLI auto-detects the preset from the template filename. Unknown template types get no semantic checks — no fake confidence.

### Readiness (preflight)

`preflight()` combines structural validation, semantic checks, template parsing, environment checks, and compliance eligibility into a single pre-render verdict without rendering:

```python
from formforge.readiness import preflight
from formforge.semantic import INVOICE_HINTS

verdict = preflight("invoice.j2.typ", data, semantic_hints=INVOICE_HINTS)
if not verdict.ready:
    for issue in verdict.errors:
        print(f"{issue.path}: {issue.message}")
```

```
formforge preflight invoice.j2.typ data.json --semantic
```

Preflight answers "can this data produce the right document?" without spending compute on Typst compilation.

With `strict=True`, partial contracts from unresolved dynamic includes are promoted from warnings to errors — readiness fails if the contract is provably incomplete:

```python
verdict = preflight("template.j2.typ", data, strict=True)
```

```
formforge preflight template.j2.typ data.json --strict
```

### Include behavior

Contract inference follows `{% include %}` directives recursively. Static includes are resolved and their data requirements are merged into the parent contract. Variables set via `{% set %}` in the parent scope are correctly excluded from the contract.

Dynamic includes (`{% include some_var %}`) and missing fragments cannot be resolved statically. They mark the contract as partial — visible via `infer_contract_with_metadata()` in the Python API and as a warning in `formforge check` and `preflight()` output.

### Inspecting contracts

```
formforge check examples/invoice.j2.typ
```

```
Template: examples/invoice.j2.typ
Fields: 12 top-level (12 required)

  * sender: object {address_line1, address_line2, email, name}
  * recipient: object {address_line1, address_line2, email, name}
  * items: list[{amount, description, num, qty, unit_price}]
  * invoice_number: scalar
  ...
```

```
formforge check examples/invoice.j2.typ --data bad_data.json
```

```
error[DATA_CONTRACT]: 3 validation error(s)
  sender: expected object, got string
  items[3].description: missing required field
  notes: expected scalar, got null
```

### Limits

- Structural types only (scalar / object / list) — no int/str/float narrowing
- `required` is a template-read heuristic, not business-semantic truth
- Semantic checks require explicit hints — no automatic business-logic inference
- Dynamic `{% include %}` produces a partial contract (warning by default; use `strict=True` to block)
- Text anomaly detection covers control characters and zero-width characters on hinted fields only — no garbage-string scoring or Unicode normalization
- Currency parsing limited to `€$£¥` symbols — other currency formats silently pass numeric checks

## ZUGFeRD / Factur-X e-invoicing

Formforge generates EN 16931 e-invoices for German domestic B2B invoicing. Generated XML passes XSD and Schematron validation in the test suite. One profile is currently supported:

| Profile | Standard | Use case |
|---------|----------|----------|
| `en16931` | EN 16931 (ZUGFeRD / Factur-X) | Domestic B2B invoices in Germany |

When `zugferd="en16931"` is set, the pipeline adds two steps after normal PDF rendering: CII XML generation from the invoice data, and embedding the XML into a PDF/A-3b container with ZUGFeRD metadata.

Pre-render validation checks required fields, currency, country, tax rate constraints, and data completeness. `preflight()` additionally runs XSD schema validation on the generated XML (requires `facturx`). One-time manual validation against the Mustang reference validator has also passed (see `docs/zugferd-prototype.md`).

ZUGFeRD and Factur-X are the same specification — ZUGFeRD is the German name, Factur-X is the French name.

**CLI:**

```
formforge render examples/einvoice.j2.typ examples/einvoice_data.json -o invoice.pdf --zugferd en16931
```

**Python API:**

```python
pdf = render(
    "examples/einvoice.j2.typ",
    "examples/einvoice_data.json",
    output="invoice.pdf",
    zugferd="en16931",
)
```

**HTTP server:**

```json
{
  "template": "einvoice.j2.typ",
  "data": { "invoice_number": "RE-2026-0042", "currency": "EUR", "seller": { ... }, ... },
  "zugferd": "en16931"
}
```

Returns 422 with `ZUGFERD_ERROR` if invoice data is missing required fields or contains unsupported shapes (allowances, charges, mixed rates). Bad `zugferd` values return 400.

The invoice data model uses raw numeric amounts (not pre-formatted strings), explicit currency codes, VAT IDs, and structured tax entries. See `examples/einvoice_data.json` for the full shape. See `docs/einvoice-scope.md` for the full supported/unsupported scenario matrix.

### Supported scope

- Profile: EN 16931 (ZUGFeRD / Factur-X)
- Country: Germany (DE)
- Currency: EUR
- Tax: standard VAT, single or mixed rates per invoice (e.g., 7% + 19%)
- Invoice type: domestic B2B standard invoice (type code 380)
- Payment: SEPA credit transfer, SEPA direct debit

### Not supported (fails loudly at validation time)

- XRechnung (code path exists, not yet schema-validated)
- Credit notes (type 381)
- Reverse charge
- Intra-community / cross-border
- Allowances, charges, or discounts
- Non-EUR currencies
- Non-DE countries

Unsupported shapes fail loudly at validation time, before any rendering or XML generation occurs.

## Generation proof

Formforge can embed a cryptographic generation proof in the PDF metadata, recording which template, which data, which engine version, and when the document was generated. This enables downstream verification that a document was produced from specific inputs without re-rendering.

This is not a digital signature (no PKI required). It is a generation proof: it answers "was this document produced from this data using this template?"

**CLI:**

```
formforge render invoice.j2.typ data.json -o out.pdf --provenance
```

**Python API:**

```python
pdf = render("invoice.j2.typ", data, output="out.pdf", provenance=True)
```

**Verification:**

```python
from formforge.provenance import verify_provenance

result = verify_provenance(pdf_bytes, "invoice.j2.typ", original_data)
print(result.verified)  # True if template + data hashes match
print(result.reason)    # "match", "data_mismatch", "template_mismatch", "no_provenance"
```

The proof records: engine name and version, SHA-256 hash of the template file, SHA-256 hash of the canonical JSON data, UTC timestamp, and a combined proof hash. It is embedded in the PDF Info dictionary and survives normal PDF handling.

Provenance works with all render modes — with or without ZUGFeRD, with or without contract validation. All flags compose.

---

## HTTP server

The server exposes two endpoints:

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/render` | Render a template to PDF |
| `GET` | `/health` | Health check |

**Successful render:**

```
curl -X POST http://localhost:8190/render \
  -H "Content-Type: application/json" \
  --data @examples/request_invoice.json \
  -o invoice.pdf
```

Returns `application/pdf` on success.

**Error response:**

```json
{
  "error": "TEMPLATE_NOT_FOUND",
  "message": "Template not found: missing.j2.typ",
  "stage": "execution",
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**Request format:** JSON object with fields `template` (required string), `data` (required object), `debug` (optional boolean), `validate` (optional boolean, defaults to true), `zugferd` (optional: `"en16931"`), `provenance` (optional boolean). See `examples/request_invoice.json` for a complete runnable example.

**Request ID:** The server accepts a client-provided `X-Request-ID` header or generates a UUID. It is echoed on both success and error responses for request tracing.

**Max request body:** 1 MB.

## Docker

**Build:**

```
docker build -t formforge .
```

**Run with bundled examples:**

```
docker run -p 8190:8190 formforge
```

**Run with custom templates:**

```
docker run -p 8190:8190 \
  -v /path/to/templates:/templates \
  formforge serve --templates /templates --host 0.0.0.0 --port 8190
```

**Mount custom fonts:**

```
docker run -p 8190:8190 \
  -v /path/to/fonts:/custom-fonts \
  -e FORMFORGE_FONT_PATH=/custom-fonts \
  formforge serve --templates /app/examples --host 0.0.0.0 --port 8190
```

The container sets `FORMFORGE_FONT_PATH=/app/fonts` by default, which includes the bundled Inter family. Override with your own fonts as shown above.

## Configuration

### Environment variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `FORMFORGE_BACKEND` | Backend selection: `typst-py` or `typst-cli` | Auto-detect |
| `FORMFORGE_FONT_PATH` | Font directory path | Bundled fonts dir |

### Backend selection

Formforge supports two render backends behind a shared protocol:

| Backend | How it works | Timeout behavior |
|---------|-------------|-----------------|
| `typst-py` | In-process Python binding | Not killable (blocks until done) |
| `typst-cli` | Subprocess calling `typst` binary | Killable via `subprocess.run(timeout=...)` |

**Library and CLI** support both backends. Auto-detect tries `typst-py` first, falls back to `typst-cli`. Override with `FORMFORGE_BACKEND`.

**Server always uses `typst-cli`**, regardless of `FORMFORGE_BACKEND`. This is intentional: the subprocess boundary is what makes server timeout actually kill a stuck render. This is a deployment-level decision, not a per-request choice.

## Fonts

Fonts are trust infrastructure. Output determinism depends on controlling font availability.

### Precedence

1. Explicit `font_paths` from caller (searched first)
2. Bundled fonts directory (searched second)
3. System fonts (Typst default, always available)

### Bundled fonts

Formforge ships Inter (Regular, Bold, Italic, BoldItalic) as TTF files. All example templates use Inter. Bundled fonts are the deterministic baseline.

### Silent fallback

Typst silently falls back when a requested font is unavailable. The PDF is valid but may use the wrong font. No error is raised in most cases.

Current observed fallback in our tested environment: Libertinus. Do not treat this as a permanent upstream guarantee.

**If you care about deterministic output, rely on bundled or explicitly supplied fonts only. Do not rely on fallback.**

### Custom fonts

| Method | Usage |
|--------|-------|
| Python API | `render(..., font_paths=["/path/to/fonts"])` |
| CLI | `--font-path /path/to/fonts` (repeatable) |
| Env var | `FORMFORGE_FONT_PATH=/path/to/fonts` |
| Docker | Mount a volume and set `FORMFORGE_FONT_PATH` |

## Templates

Templates are Jinja2-preprocessed Typst files (`.j2.typ`). Jinja2 handles data binding; Typst handles layout and PDF generation.

```
{{ variable }}              Interpolate a value (auto-escaped)
{% for item in items %}     Loop
{% if condition %}          Conditional
{{ value | typst_money }}   Filter
```

Raw Typst files (`.typ`) are also supported but receive no data binding or escaping. They are for template authors who want direct Typst control. Formforge's safety guarantees apply to Jinja-interpolated values in `.j2.typ` templates.

### Escaping

All string values interpolated via `{{ }}` are automatically escaped for Typst text/content contexts. This is text-interpolation safety only, not universal Typst sanitization.

11 characters are escaped: `\` `$` `#` `@` `{` `}` `<` `` ` `` `~` `[` `]`

Intentionally not escaped: `_` and `*` (word-boundary emphasis; escaping everywhere would damage normal text like `snake_case`).

**Not in scope:** code mode, math mode, and other context-sensitive Typst syntax. Templates that embed user data in those contexts require author discipline.

### Filters

| Filter | Purpose | Escaping |
|--------|---------|----------|
| `typst_money` | Color-wrap negative currency values | Escapes input, returns markup |
| `typst_color` | Wrap value in colored text | Escapes input, returns markup |
| `typst_markup` | Bypass auto-escaping | **Unsafe for user input** |

`typst_markup` exists for template authors who need to emit controlled Typst formatting. Never pass arbitrary user data through it.

### Template rules

Templates may format values, loop through rows, conditionally show blocks, and render precomputed strings. Templates must not perform business logic (currency calculation, tax computation, rounding). Those values should arrive precomputed in the data.

## Timeout and debug

### Server timeout

The server render timeout defaults to 30 seconds. Timeout is real: the CLI subprocess is killed via `subprocess.run(timeout=...)`. A secondary async watchdog (`timeout + 5s`) provides a defensive backstop in case subprocess cleanup stalls. The watchdog should never fire in normal operation.

### Artifact policy

| Scenario | Intermediate `.typ` file |
|----------|-------------------------|
| Successful render | Cleaned up |
| Compile error | Preserved (even without debug) |
| Timeout (no debug) | Cleaned up |
| Timeout (debug mode) | Preserved |
| `--debug` flag or `"debug": true` | Always preserved |

Compile errors preserve the intermediate file even without debug mode because the generated Typst markup is often required to diagnose the failure. Timeout behavior is stricter: intermediates are cleaned to prevent accumulating orphan artifacts under repeated timeout failures, unless debug mode is explicitly enabled.

Intermediate files are written next to the template as `_formforge_*.typ`. They contain the Jinja2-rendered Typst markup before compilation.

## Error model

### Error codes

| Code | Meaning |
|------|---------|
| `INVALID_DATA` | Bad input data (not a dict, bad JSON, wrong type) |
| `TEMPLATE_NOT_FOUND` | Template file does not exist |
| `TEMPLATE_SYNTAX` | Jinja2 syntax error in the template |
| `TEMPLATE_VARIABLE` | Undefined variable during Jinja2 rendering |
| `MISSING_ASSET` | Referenced file (image, etc.) not found |
| `MISSING_FONT` | Font not available (rare due to silent fallback) |
| `COMPILE_ERROR` | Typst compilation failed |
| `DATA_CONTRACT` | Data does not satisfy template's structural contract |
| `ZUGFERD_ERROR` | ZUGFeRD invoice data validation or XML generation failed |
| `RENDER_TIMEOUT` | Render exceeded the time limit |
| `BACKEND_ERROR` | Unexpected backend failure |

### Pipeline stages

| Stage | Where |
|-------|-------|
| `data_resolution` | Parsing/validating input data |
| `data_validation` | Validating data against template contract (default for .j2.typ) |
| `zugferd_validation` | Validating invoice data against EN 16931 requirements |
| `template_preprocess` | Jinja2 rendering |
| `compilation` | Typst compilation to PDF |
| `zugferd` | ZUGFeRD XML generation and PDF post-processing |
| `execution` | Server/CLI execution wrapper |

Server error responses include `error`, `message`, `stage`, and `request_id`. With `debug: true`, responses also include `detail` (full Typst diagnostic) and file paths.

## What is working and tested

- `formforge.render()` produces valid PDFs from dict/JSON + Jinja2 templates
- CLI `render` and `serve` commands
- HTTP server with request validation, structured errors, request ID tracking
- Server timeout kills stuck renders (subprocess boundary)
- Auto-escaping: 11 Typst special characters in text-interpolation contexts
- Bundled Inter fonts, deterministic across local and container environments
- Library and CLI support both backends; server forces typst-cli
- Docker: builds, runs, produces matching output
- 5 starter templates: invoice, statement, receipt, letter, report
- Pre-render contract validation: default for `.j2.typ` — catches missing/wrong fields before Jinja runs
- Include-aware contract inference: follows `{% include %}` fragments recursively, marks dynamic includes as partial
- Semantic validation: hint-driven arithmetic, date, completeness, numeric coercion, and balance reconciliation checks
- Semantic presets: `INVOICE_HINTS`, `RECEIPT_HINTS`, `STATEMENT_HINTS` — auto-detected by template name in CLI
- `formforge check` CLI for template introspection and data validation
- ZUGFeRD / Factur-X: EN 16931 e-invoice generation for DE domestic B2B (PDF/A-3b + embedded CII XML, schema-tested)
- Generation proof: cryptographic provenance embedded in PDF metadata, verifiable without re-rendering
- 688 tests passing (unit, integration, contract, include inference, semantic, ZUGFeRD, provenance, audit, ugly-data pressure, diagnostics)

## Development

### Quick setup

```
make dev
source .venv/bin/activate
```

Or manually:

```
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Verify environment

```
formforge doctor           # check everything
formforge doctor --smoke   # include render + server health smoke test
```

### Common tasks

```
make test     # run pytest
make lint     # run ruff check + format check
make smoke    # quick render + server health verification
make clean    # remove build artifacts
make docker   # build Docker image
make help     # list all targets
```

`make setup` creates a standard (non-editable) install. `make dev` creates an editable install with dev dependencies.

## Caveats

- Silent font fallback means missing fonts may not produce errors — just wrong output
- Source mapping from generated Typst back to Jinja2 template source is limited
- `typst_markup()` intentionally bypasses escaping — template author's responsibility
- Code/math mode contexts are not auto-escaped
- Line-start markup (`=` headings, `-` lists) is template layout, not auto-escaped
- Font determinism across arbitrary environments is not fully soak-tested
- Dynamic `{% include %}` marks contract as partial (warning, not error)
- Semantic hints for letter and report templates are not yet built — CLI reports "no semantic hints configured"
- Standard install from source is the most reliable local path today
- Not yet published to PyPI

## Bundled templates

| Template | File | Tests |
|----------|------|-------|
| Invoice | `examples/invoice.j2.typ` | Single and multi-page, ugly data |
| E-Invoice (ZUGFeRD) | `examples/einvoice.j2.typ` | EN 16931, numeric data, VAT IDs |
| Statement | `examples/statement.j2.typ` | Multi-page tables, negative values |
| Receipt | `examples/receipt.j2.typ` | Long items, many items |
| Letter | `examples/letter.j2.typ` | Long subject, many paragraphs, enclosures |
| Report | `examples/report.j2.typ` | Metrics, incidents, conditional formatting |

Each has a matching `_data.json` file in `examples/`.
