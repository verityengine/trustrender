# Pagination Soak Results

Date: 2026-04-11 11:39
Platform: darwin, Python 3.12.13
Backend: typst-cli (subprocess, production server path)
RSS start: 34.1 MB, RSS end: 58.8 MB

## Render Performance

| Fixture | Rows | Pages | Size | Iters | P50 | P95 | P99 | Max | ms/row |
|---------|------|-------|------|-------|-----|-----|-----|-----|--------|
| invoice-50 | 50 | 3 | 130 KB | 20 | 61.9 ms | 65.6 ms | 79.6 ms | 83.1 ms | 1.25 |
| invoice-1000 | 1000 | 33 | 1915 KB | 10 | 211.1 ms | 214.6 ms | 215.2 ms | 215.3 ms | 0.21 |
| statement-201 | 201 | 7 | 498 KB | 20 | 94.5 ms | 97.6 ms | 110.8 ms | 114.1 ms | 0.47 |
| statement-1000 | 1000 | 29 | 2324 KB | 10 | 259.9 ms | 266.6 ms | 268.2 ms | 268.6 ms | 0.26 |
| report-dense | 115 | 8 | 214 KB | 20 | 71.6 ms | 76.4 ms | 81.6 ms | 82.9 ms | 0.63 |

## Observations

Numbers above are measured, not targets.
