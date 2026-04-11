# TrustRender

Generate structured business PDFs from data + templates. No browser, no Chromium.

TrustRender renders invoices, statements, receipts, and similar structured documents using [Typst](https://typst.app/) as the layout engine and Jinja2 for data binding. It ships as a Python library, CLI, and HTTP server.

**Not** an HTML-to-PDF converter, headless browser, visual editor, or multi-format platform. It does one thing: structured business PDFs from code.

## Install

```
git clone https://github.com/verityengine/trustrender.git
cd trustrender
pip install .
```

Requires Python 3.11+ and the Typst CLI binary (`brew install typst` on macOS, or [typst.app](https://typst.app/)).

For development: `pip install -e ".[dev]"` or `make dev`.

### Verify

```
trustrender doctor --smoke
```

Checks Python version, backends, fonts, and runs a real render + server health check.

## Quick start

**Python:**

```python
from trustrender import render

pdf = render("examples/invoice.j2.typ", "examples/invoice_data.json", output="invoice.pdf")
```

**CLI:**

```
trustrender render examples/invoice.j2.typ examples/invoice_data.json -o invoice.pdf
```

**Server:**

```
trustrender serve --templates examples/ --port 8190
curl -X POST http://localhost:8190/render \
  -H "Content-Type: application/json" \
  --data @examples/request_invoice.json -o invoice.pdf
```

## Why TrustRender

### Validated before render

Every `render()` call on a `.j2.typ` template validates data against the template's inferred contract by default. Missing fields, null values, and wrong structural types are rejected with specific field-level errors before Typst compilation starts.

```
TrustRenderError: Data validation failed: 11 field errors in invoice.j2.typ
  sender: missing required field (expected: object)
  items: missing required field (expected: list[object])
  invoice_date: missing required field
```

`preflight()` goes further: structural validation, semantic checks, font verification, compliance eligibility, and text safety scanning — all without rendering.

### No browser dependency

No Chromium, no Puppeteer, no headless browser. Typst compiles directly to PDF. The server runs renders as killable subprocesses with real timeout enforcement.

Measured: 1,000-row invoice renders in 211ms (33 pages). Server throughput: 53.8 RPS. Peak RSS: 69.5 MB.

### EN 16931 e-invoicing

Generates ZUGFeRD / Factur-X compliant invoices for German domestic B2B. PDF/A-3b output with embedded CII XML, validated by XSD and Schematron before embedding.

```
trustrender render einvoice.j2.typ data.json -o invoice.pdf --zugferd en16931
```

Supported: DE, EUR, standard VAT (single or mixed rates), invoices and credit notes.
Not supported (fails loudly): reverse charge, cross-border, allowances/charges, non-EUR.

See [docs/einvoice-scope.md](docs/einvoice-scope.md) for the full scope matrix.

### Output provenance

Embeds a cryptographic generation proof in the PDF: template hash, data hash, engine version, timestamp, and a combined proof hash. Verifiable without re-rendering.

```python
from trustrender.provenance import verify_provenance
result = verify_provenance(pdf_bytes, "invoice.j2.typ", original_data)
# result.verified → True if hashes match
```

Not a digital signature. A generation proof: "was this document produced from this data using this template?"

## CLI

```
trustrender render <template> <data.json> -o <output.pdf> [--zugferd en16931] [--provenance] [--no-validate]
trustrender preflight <template> <data.json> [--semantic] [--strict]
trustrender check <template> [--data <data.json>]
trustrender serve --templates <dir> [--port 8190] [--dashboard] [--history <path>]
trustrender audit <template> <data.json> -o <output.pdf> [--baseline-dir <dir>]
trustrender doctor [--smoke]
```

Full flag reference: `trustrender <command> --help`.

## HTTP server

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/render` | Render template to PDF |
| `POST` | `/preflight` | Pre-render readiness check |
| `GET` | `/health` | Health check |
| `GET` | `/template-source?name=` | Raw template source |
| `GET` | `/history` | Render trace list (requires `--history`) |
| `GET` | `/dashboard` | Ops dashboard (requires `--dashboard`) |

Backpressure: max 8 concurrent renders (configurable), 503 when at capacity.
Max body: 10 MB (configurable). Timeout: 30s (subprocess killed on expiry).

See [docs/server.md](docs/server.md) for full API detail, error model, and configuration.

## Bundled templates

| Template | File | Description |
|----------|------|-------------|
| Invoice | `examples/invoice.j2.typ` | Standard invoice with line items |
| E-Invoice | `examples/einvoice.j2.typ` | ZUGFeRD EN 16931 compliant |
| Statement | `examples/statement.j2.typ` | Account/transaction statement |
| Receipt | `examples/receipt.j2.typ` | Point-of-sale receipt |
| Letter | `examples/letter.j2.typ` | Business letter |
| Report | `examples/report.j2.typ` | Executive report with metrics |

Each has a matching `_data.json` file in `examples/`.

## Docker

```
docker build -t trustrender .
docker run -p 8190:8190 trustrender
```

Mount custom templates or fonts:

```
docker run -p 8190:8190 \
  -v /path/to/templates:/templates -e TRUSTRENDER_TEMPLATES_DIR=/templates \
  -v /path/to/fonts:/fonts -e TRUSTRENDER_FONT_PATH=/fonts \
  trustrender
```

## Configuration

| Variable | Purpose | Default |
|----------|---------|---------|
| `TRUSTRENDER_BACKEND` | `typst-py` or `typst-cli` | Auto-detect |
| `TRUSTRENDER_FONT_PATH` | Font directory | Bundled Inter fonts |
| `TRUSTRENDER_TEMPLATES_DIR` | Template directory for `serve` | — |
| `TRUSTRENDER_MAX_BODY_SIZE` | Max request body (bytes) | 10 MB |

## Development

```
make dev                    # editable install + dev deps
trustrender doctor --smoke  # verify environment
make test                   # pytest
make lint                   # ruff
make docker                 # build image
make help                   # all targets
```

837 tests (unit, integration, contract, semantic, ZUGFeRD, provenance, ugly-data, font, pagination, text safety, Schematron).

## Documentation

| Topic | Link |
|-------|------|
| Validation & readiness | [docs/validation.md](docs/validation.md) |
| E-invoice scope matrix | [docs/einvoice-scope.md](docs/einvoice-scope.md) |
| HTTP server & error model | [docs/server.md](docs/server.md) |
| Templates & escaping | [docs/templates.md](docs/templates.md) |
| Fonts | [docs/fonts.md](docs/fonts.md) |
| Provenance | [docs/provenance.md](docs/provenance.md) |
| Known limits | [docs/known-limits.md](docs/known-limits.md) |

## Caveats

- Typst silently substitutes fonts when a declared font is missing — `preflight` and `doctor` catch this for configured font paths, but the render path itself does not error
- Source mapping from generated Typst back to Jinja2 source is limited
- `typst_markup()` intentionally bypasses escaping — template author's responsibility
- Code/math mode contexts are not auto-escaped (text-interpolation only)
- Not yet published to PyPI — install from source
