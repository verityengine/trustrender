# Typst Evaluation Results

Date: 2026-04-10
Environment: macOS (Apple Silicon), Python 3.12.13, Typst CLI 0.14.2, typst-py 0.14.8

---

## What changed

- Recreated virtualenv (was broken — hardcoded to wrong path)
- Installed Typst CLI 0.14.2 via Homebrew
- Installed typst-py 0.14.8 (Python binding by messense)
- Installed Jinja2 3.1.6
- Installed WeasyPrint 68.1 (for comparison)
- Created placeholder logo PNG
- Created 4 invoice templates:
  - `examples/invoice_simple.typ` — 1-page static invoice
  - `examples/invoice_multipage.typ` — 3-page static invoice (45 line items)
  - `examples/invoice_sysinputs.typ` — data-bound via sys.inputs
  - `examples/invoice.j2.typ` — data-bound via Jinja2 preprocessing
- Created benchmark harness: `benchmarks/bench_typst.py`, `benchmarks/bench_weasyprint.py`
- Created sample data: `examples/invoice_data.json`
- Created end-to-end render script: `examples/render_test.py`

---

## What works now

### Rendering
- Typst CLI compiles invoice PDFs correctly
- Typst Python binding compiles invoice PDFs correctly
- Both produce valid, visually identical output
- PNG rendering works via Python binding (`format='png'`)

### Visual quality (verified)
- Logo renders at correct size and position
- Table columns align cleanly
- Long descriptions wrap correctly within table cells
- Currency values right-align properly
- Page header/footer display on every page
- Page numbers display correctly ("Page 1 of 3" format)
- Table headers repeat on page breaks
- No broken row splitting across page boundaries
- Multi-page invoice (45 items, 3 pages) paginates correctly

### Data binding
- **sys.inputs:** works, but requires flattening nested data to string key-value pairs and serializing arrays as JSON strings
- **Jinja2 preprocessing:** works well with auto-escaping of Typst special characters (`$`, `#`, `@`, `\`)
- In-memory PDF bytes return works (temp `.typ` file required for image path resolution)

### Error messages
- Missing image: `"file not found (searched at /path/to/file)"` — actionable
- Bad type: `"expected length, found string"` — clear
- Unclosed delimiter: `"unclosed delimiter"` — minimal but sufficient
- Undefined variable: `"unknown variable: name"` — clear
- Missing dict key: `"dictionary does not contain key 'X' and no default value was specified"` — good
- **Gap:** Python binding loses line numbers and source context that the CLI provides

---

## What is unproven

- Font handling across Linux/macOS/containers (only tested macOS with system fonts)
- Behavior with custom fonts bundled in the project
- SVG embedding quality
- Performance under concurrent load
- Template error messages through the Jinja2 pipeline (two error surfaces: Jinja2 + Typst)
- Deployment in Docker/serverless containers
- How Typst handles very large documents (100+ pages)
- Whether `typst-py` version will track Typst CLI releases reliably

---

## Benchmarks

All numbers measured on Apple Silicon Mac. 100 iterations per warm measurement.

### Typst

| Document | Cold | Median | Min | Max |
|----------|------|--------|-----|-----|
| Simple invoice (1 page, static) | 67ms | 41ms | 39ms | 65ms |
| Multi-page invoice (3 pages, static) | 82ms | 42ms | 40ms | 52ms |
| Jinja2 pipeline (1 page, JSON→Jinja→Typst→PDF) | 46ms | 41ms | 39ms | 63ms |

- Peak RSS: 365 MB (includes Python runtime + Typst engine in-process)
- typst-py package size: 48 MB (self-contained Rust binary)

### WeasyPrint

| Document | Cold | Median | Min | Max |
|----------|------|--------|-----|-----|
| Simple invoice (1 page, HTML) | 118ms | 96ms | 92ms | 129ms |

- Peak RSS: 170 MB
- Depends on: Pillow, fonttools, tinycss2, tinyhtml5, pydyf, cffi, and system libs

### Comparison (simple invoice, warm median)

| Metric | Typst | WeasyPrint | Notes |
|--------|-------|------------|-------|
| Render time | 41ms | 96ms | Typst ~2.3x faster |
| Cold start | 67ms | 118ms | Typst ~1.8x faster |
| Peak RSS | 365 MB | 170 MB | Typst uses more (Rust engine in-process) |
| PDF size | 53 KB | 51 KB | Comparable |
| Package deps | 1 (self-contained) | 12+ packages + system libs | Typst simpler to deploy |
| Multi-page cost | +1ms (42ms) | not tested | Pagination adds negligible cost |

### Key observation
- Jinja2 preprocessing overhead is negligible (~0ms over raw Typst compile)
- Multi-page pagination adds negligible cost (~1ms for 3 pages vs 1 page)
- Typst's higher RSS is the Rust engine loaded into the Python process — a one-time cost

---

## Risks

1. **Python binding error surface:** Line numbers and source context are lost. Developers debugging template issues would need the intermediate `.typ` file or the CLI for better diagnostics. Solvable but needs attention.

2. **Typst special character escaping:** `$`, `#`, `@` in data values will break Typst if not escaped. Auto-escape via Jinja2 `finalize` works but must be wired into the product layer. If missed, errors are confusing.

3. **Image path resolution:** In-memory compilation requires a temp `.typ` file written to the template directory (so relative image paths resolve). Fully in-memory with virtual file dict doesn't support binary assets. This means the render pipeline always touches disk for the `.typ` source.

4. **typst-py maintenance:** The Python binding is maintained by one person (messense). If it falls behind or is abandoned, we'd fall back to subprocess calls to the CLI, which is viable but slower for high-throughput use.

5. **Memory footprint:** 365 MB peak RSS is significant for serverless/container deployment. Needs investigation on whether this is baseline or scales with document complexity.

---

## Decision gate

### 1. Can Typst render invoice-grade PDFs well enough?
**Yes.** Output quality is strong. Tables, headers/footers, page numbers, image embedding, multi-page pagination with repeated headers all work correctly. Text wrapping behaves well. Layout is clean and professional.

### 2. Can Python integration support a clean product API?
**Yes, with caveats.** The `typst-py` binding works for compilation and returns PDF bytes. The main caveat is error diagnostics — the binding loses line numbers that the CLI provides. The API shape (`typst.compile(path, format='pdf')`) is clean enough for wrapping.

### 3. Is Jinja → Typst → PDF actually pleasant enough to be the MVP architecture?
**Yes.** Jinja2 templates with Typst markup are readable. The `{{ variable }}` syntax coexists with Typst's `#` syntax cleanly. Auto-escaping handles the `$`/`#` conflict. The two-stage compilation (Jinja2 render → Typst compile) adds negligible latency. Debugging requires inspecting the intermediate `.typ` file, which is acceptable.

### 4. What is the biggest blocker?
**Error diagnostics.** The Python binding strips source location from errors. For the product to have a good developer experience, we need to either:
- Save and expose the intermediate `.typ` file on error
- Use subprocess to the CLI to capture full diagnostics
- Or contribute line-number support upstream to typst-py

This is solvable but it's the gap between "it works" and "it's pleasant to use."

### 5. Should we proceed, fallback to WeasyPrint, or stop?
**Proceed with Typst.**

Typst is 2.3x faster, has simpler deployment (single self-contained package vs system library dependencies), handles pagination natively, and the template syntax is readable. WeasyPrint's advantages (lower RSS, HTML familiarity) don't outweigh Typst's strengths for this use case.

---

## Next best step

Build the core `trustrender` Python API:
- `trustrender.render(template_path, data_dict) -> bytes` (the main entry point)
- Jinja2 auto-escaping built in
- Intermediate `.typ` file preserved on error for debugging
- CLI command: `trustrender render template.j2.typ data.json -o output.pdf`
