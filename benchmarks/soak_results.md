# Soak Test Results

Last run: 2026-04-10
Platform: macOS (Apple Silicon), Python 3.12, typst-py backend
Test count at time of run: 592

---

## Library Soak (500 renders, sequential)

| Metric | Value |
|--------|-------|
| Iterations | 500 |
| Fixtures | 7 (invoice, statement, receipt, letter, report + long variants) |
| Total time | 30.1s |
| Throughput | 16.6 RPS |
| Errors | 0 |
| Temp file leaks | 0 |

### Latency

| Percentile | ms |
|------------|-----|
| avg | 60.1 |
| p50 | 53.3 |
| p95 | 95.0 |
| max | 313.0 |
| min | 45.0 |

### Memory

| Metric | Value |
|--------|-------|
| RSS start | 26.7 MB |
| RSS end | 436.8 MB |
| RSS drift | 410.1 MB |

Note: RSS growth is the typst-py working set (in-process Typst engine initialization + font cache), not a memory leak. RSS stabilizes after ~200 renders (no further growth from iteration 200 to 500).

---

## Mixed Soak (200 renders, valid + invalid interleaved)

| Metric | Value |
|--------|-------|
| Iterations | 200 |
| Total time | 4.8s |
| Unexpected outcomes | 0 |
| Temp file leaks | 0 |

### Outcome distribution

| Outcome | Count |
|---------|-------|
| success | 87 |
| DATA_CONTRACT (expected) | 85 |
| TEMPLATE_VARIABLE (expected) | 28 |
| unexpected | 0 |

### Latency

| Percentile | ms |
|------------|-----|
| avg | 23.8 |
| p50 | 1.8 |
| p95 | 57.9 |
| max | 80.6 |
| min | 0.6 |

Note: p50 is low because contract validation failures are caught before Typst compilation runs.

### Memory

| Metric | Value |
|--------|-------|
| RSS start | 26.6 MB |
| RSS end | 371.0 MB |
| RSS drift | 344.4 MB |

---

## Server Soak (not run this session)

Server soak requires a running server (`trustrender serve --templates examples --port 8192`). Previous manual run (documented in docs/outreach.md):

| Metric | Value |
|--------|-------|
| Iterations | 300 |
| Workers | 5 concurrent |
| Throughput | 53.8 RPS |
| Errors | 0 |
| Temp file leaks | 0 |
| Avg latency | 89ms |

---

## Key Observations

1. **Zero errors** across 700 total renders (library + mixed)
2. **Zero temp file leaks** — artifact cleanup is working correctly
3. **Memory stabilizes** — no unbounded growth, RSS plateaus after engine initialization
4. **Error paths work** — contract validation and template errors fire correctly and are classified into the right error codes
5. **Latency is stable** — no degradation over 500 sequential renders

## How to reproduce

```
python benchmarks/soak_test.py --library -n 500
python benchmarks/soak_test.py --mixed -n 200
```

For server soak:
```
trustrender serve --templates examples --port 8192 &
python benchmarks/soak_test.py --server -n 300
```
