# Table Pagination Proof

TrustRender handles multi-page structured business tables cleanly without browser rendering.

## What was rendered

Two fixtures using the existing bundled templates with extended data:

| Fixture | Template | Rows | Pages | File size | Render time |
|---------|----------|------|-------|-----------|-------------|
| 50-row invoice | `invoice.j2.typ` | 50 line items | 3 | 130 KB | 0.13s |
| 200-row statement | `statement.j2.typ` | 201 transactions | 7 | 498 KB | 0.09s |

## What was verified

- **Tables break across pages correctly.** Both fixtures produce multi-page output with clean page breaks mid-table.
- **Headers repeat.** Typst's `table.header()` automatically repeats column headers on each page. Both templates use this.
- **No row truncation observed.** Verified via text extraction (`pdftotext`): the invoice contains all 50 item descriptions (e.g., "Website redesign" appears 3 times for 3 occurrences in 50 items). The statement contains all 201 transaction rows — "Monthly hosting fee", "Payment received", "API usage", and "Software license" each appear 10 times (200 rows / 20 unique descriptions). The statement intermediate Typst file contains 202 `table.hline` entries (1 header separator + 201 row separators).
- **Repeating headers verified.** The statement's "Date" and "Ref" column headers appear 6 times across 7 pages (once per continuation page). The invoice's "Description" header appears on multiple pages.
- **Local and Docker output match.** Byte-identical content between local and Docker renders (only PDF metadata timestamps differ).

## How to reproduce

```
# 50-row invoice (3 pages)
trustrender render examples/invoice.j2.typ examples/invoice_long_data.json -o invoice_long.pdf

# 200-row statement (7 pages)
trustrender render examples/statement.j2.typ examples/statement_long_data.json -o statement_long.pdf
```

Docker:

```
docker build -t trustrender .
docker run --rm -v $(pwd)/examples:/app/examples \
  trustrender render /app/examples/invoice.j2.typ /app/examples/invoice_long_data.json \
  -o /app/examples/invoice_long.pdf
```

## Why this matters

Backend teams generating invoices and statements need tables that paginate correctly without manual page-break logic. TrustRender delegates pagination to Typst's layout engine, which handles:

- Automatic page breaks when table content exceeds the page
- Repeating table headers on continuation pages
- Correct page numbering in footers
- Consistent output across local and container environments

No headless browser, no Chromium, no manual pagination code.

## Automated verification

19 automated tests in `tests/test_pagination.py` verify pagination behavior across all scales:

| Scale | Template | Rows | Pages | What is verified |
|-------|----------|------|-------|-----------------|
| Standard | invoice | 10 | 1 | Single-page baseline |
| Medium | invoice | 50 | 3 | Page count, all rows present, headers repeat, total present |
| Medium | statement | 201 | 7 | Page count, spot-check rows, headers repeat on 5+ pages, closing balance |
| Large | invoice | 1000 | 33 | Page count, first/middle/last items, headers on 20+ pages |
| Large | statement | 1000 | 29 | Page count, spot-check rows, headers on 15+ pages |
| Dense | report | 115 entries | 8 | Page count, all sections present (metrics, incidents, spend, recommendations) |

Text extraction uses pypdf (already a dependency). Assertions use `>=` thresholds to avoid brittleness from minor layout changes.

## Large-document soak results

80 renders across 5 fixture sizes, CLI subprocess backend, zero errors:

| Fixture | Rows | Pages | P50 | P95 | ms/row |
|---------|------|-------|-----|-----|--------|
| invoice-50 | 50 | 3 | 63.5 ms | 74.6 ms | 1.32 |
| invoice-1000 | 1000 | 33 | 217.6 ms | 246.3 ms | 0.22 |
| statement-201 | 201 | 7 | 96.7 ms | 100.7 ms | 0.48 |
| statement-1000 | 1000 | 29 | 271.1 ms | 278.9 ms | 0.27 |
| report-dense | 115 | 8 | 77.7 ms | 96.6 ms | 0.70 |

Peak RSS: 60.5 MB after all 80 renders. Full results: `benchmarks/pagination_soak_results.md`.

## Limitations

- Pagination is handled by Typst's layout engine. TrustRender does not add custom pagination logic.
- Row height is determined by content — very tall rows may split awkwardly at page boundaries (standard Typst behavior).
- No explicit "page break before total" control in the current templates. Totals render wherever they fall after the last row.
