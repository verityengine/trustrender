# Soak Test Results

Formforge runtime stability verified under sustained repeated rendering with mixed success and failure conditions.

## Test Environment

- macOS, Python 3.12.13, Typst 0.14.2
- typst-py backend (library tests), typst-cli subprocess backend (server tests)
- Bundled Inter fonts, existing example templates

## Results Summary

| Test | Iterations | Errors | Temp file leaks | RPS |
|------|-----------|--------|-----------------|-----|
| Library soak (sequential) | 500 | 0 | 0 | 17.8 |
| Mixed success/failure | 200 | 0 unexpected | 0 | 45.5 |
| Server concurrent (5 workers) | 300 | 0 | 0 | 53.8 |

## Library Soak (500 renders)

Sequential renders across all 7 fixtures (5 standard templates + 2 long pagination fixtures).

- **0 errors** in 500 renders
- **0 temp files** before or after (cleanup working)
- **Latency**: avg 56ms, p50 50ms, p95 88ms, max 315ms
- **RSS peak**: 439 MB — stabilizes after ~100 iterations, no growth from iteration 200 to 500

## Mixed Success/Failure (200 renders)

Interleaved valid renders, contract validation failures (DATA_CONTRACT), and template errors (TEMPLATE_VARIABLE).

| Outcome | Count | Expected |
|---------|-------|----------|
| Success | 87 | 87 |
| DATA_CONTRACT | 85 | 85 |
| TEMPLATE_VARIABLE | 28 | 28 |
| Unexpected | 0 | 0 |

- **0 unexpected outcomes** — every render produced the expected result
- **0 temp files** accumulated
- **Latency**: avg 22ms, p50 1.6ms (contract failures are fast), p95 52ms, max 80ms
- Error paths do not destabilize the process

## Server Concurrent (300 renders)

5 concurrent workers sending bursts of 10 requests. Mix of standard and long invoice data.

- **0 errors** in 300 renders
- **0 temp files** before or after
- **Latency**: avg 89ms, p50 84ms, p95 120ms, max 304ms
- **53.8 requests/second** sustained over 30 batches

## Memory Interpretation

RSS is measured via `resource.getrusage(RUSAGE_SELF).ru_maxrss`. On macOS, this reports **peak RSS** (high-water mark), not current RSS. The peak rises during the first ~100 iterations as the Typst engine initializes and caches internally, then stabilizes. No late-run memory growth observed. This is consistent with initialization overhead, not a memory leak.

For definitive leak detection, a Linux environment with `/proc/self/status` VmRSS tracking or a profiler like `memray` would be more precise. The macOS peak-RSS stability is a reasonable signal for v1.

## Temp File Cleanup

All three tests started and ended with 0 temp files in the examples/ directory. Temp files (`_formforge_*.typ`) are created during Jinja2 preprocessing and cleaned up on success. Error-path cleanup was verified in the mixed test (85 contract failures + 28 template errors, all cleaned up).

## What This Proves

- Formforge does not obviously leak temp artifacts under repeated use
- Formforge does not obviously ratchet memory upward after warmup
- Error paths (contract validation, template errors) stay classified and contained
- The server handles sustained concurrent load without errors
- Cleanup behavior is correct for both success and failure paths

## What This Does Not Prove

- Behavior under memory pressure or OOM conditions
- Behavior with hundreds of concurrent connections
- Long-duration (hours/days) stability
- Linux production environment behavior (tested on macOS only)

## How to Reproduce

```
# Library + mixed soak (no server needed)
python benchmarks/soak_test.py --library --mixed

# Server soak (start server first)
formforge serve --templates examples --port 8192
python benchmarks/soak_test.py --server
```
