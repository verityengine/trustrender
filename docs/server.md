# HTTP Server

## Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST` | `/render` | Render a template to PDF |
| `POST` | `/preflight` | Pre-render readiness check (no rendering) |
| `GET` | `/template-source?name=` | Raw template source (for browser editing) |
| `GET` | `/health` | Health check |
| `GET` | `/history` | Render trace history (requires `--history`) |
| `GET` | `/history/{id}` | Single trace detail |
| `GET` | `/stats` | Aggregate render statistics |
| `GET` | `/dashboard` | Ops dashboard UI (requires `--dashboard`) |

## Starting the server

```
trustrender serve --templates ./templates --port 8190
trustrender serve --templates ./templates --dashboard --history ./history.db
```

## Request format

JSON object with fields:

| Field | Type | Required | Default |
|-------|------|----------|---------|
| `template` | string | yes | — |
| `data` | object | yes | — |
| `validate` | boolean | no | `true` |
| `debug` | boolean | no | `false` |
| `zugferd` | string | no | — |
| `provenance` | boolean | no | `false` |
| `template_source` | string | no | — |

`template_source` enables ephemeral template editing — the server writes a temp file, runs the pipeline, and cleans up. The `template` field is still required for include resolution and preset detection.

See `examples/request_invoice.json` for a complete runnable example.

## Successful render

```
curl -X POST http://localhost:8190/render \
  -H "Content-Type: application/json" \
  --data @examples/request_invoice.json \
  -o invoice.pdf
```

Returns `application/pdf` with `X-Request-ID` and `X-Trace-ID` headers.

## Error responses

```json
{
  "error": "TEMPLATE_NOT_FOUND",
  "message": "Template not found: missing.j2.typ",
  "stage": "execution",
  "request_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

With `debug: true`, responses also include `detail` (full Typst diagnostic) and file paths.

## Error codes

| Code | Meaning |
|------|---------|
| `INVALID_DATA` | Bad input data (not a dict, bad JSON, wrong type) |
| `TEMPLATE_NOT_FOUND` | Template file does not exist |
| `TEMPLATE_SYNTAX` | Jinja2 syntax error |
| `TEMPLATE_VARIABLE` | Undefined variable during Jinja2 rendering |
| `MISSING_ASSET` | Referenced file (image, etc.) not found |
| `MISSING_FONT` | Font not available (rare due to silent fallback) |
| `COMPILE_ERROR` | Typst compilation failed |
| `DATA_CONTRACT` | Data does not satisfy template's structural contract |
| `ZUGFERD_ERROR` | ZUGFeRD validation or XML generation failed |
| `RENDER_TIMEOUT` | Render exceeded the time limit |
| `BACKEND_ERROR` | Unexpected backend failure |

## Pipeline stages

| Stage | Where |
|-------|-------|
| `data_resolution` | Parsing/validating input data |
| `data_validation` | Validating data against template contract |
| `zugferd_validation` | Validating invoice data against EN 16931 |
| `template_preprocess` | Jinja2 rendering |
| `compilation` | Typst compilation to PDF |
| `zugferd` | ZUGFeRD XML generation and PDF post-processing |
| `execution` | Server/CLI execution wrapper |

## Backpressure

Max concurrent renders defaults to 8 (configurable via `--max-concurrent`). Requests at capacity receive 503.

## Timeout

Server render timeout: 30 seconds. The CLI subprocess is killed via `subprocess.run(timeout=...)`. A secondary async watchdog (`timeout + 5s`) provides a defensive backstop.

## Artifact policy

| Scenario | Intermediate `.typ` file |
|----------|-------------------------|
| Successful render | Cleaned up |
| Compile error | Preserved (for diagnosis) |
| Timeout (no debug) | Cleaned up |
| `debug: true` | Preserved |

## Request ID

The server accepts a client-provided `X-Request-ID` header or generates a UUID. Echoed on all responses.

## Backend

The server always uses `typst-cli` regardless of `TRUSTRENDER_BACKEND`. The subprocess boundary is what makes timeout kill a stuck render.
