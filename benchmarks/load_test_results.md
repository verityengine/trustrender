# Load Test Results

Date: 2026-04-11 10:03
Platform: darwin, Python 3.12.13
Server max_concurrent_renders: 8


### Pass 1: invoice.j2.typ (simple PDF)

| Concurrency | Requests | OK | 503 | Errors | p50 (ms) | p95 (ms) | p99 (ms) | Max (ms) | RPS | RSS (MB) |
|-------------|----------|----|-----|--------|----------|----------|----------|----------|-----|----------|
| 20 | 50 | 8 | 42 | 0 | 144.0 | 168.0 | 168.5 | 168.6 | 47.1 | 48.6 |
| 50 | 100 | 11 | 89 | 0 | 191.4 | 220.5 | 231.6 | 234.4 | 42.1 | 51.9 |
| 100 | 100 | 12 | 88 | 0 | 185.6 | 208.7 | 208.9 | 209.0 | 45.0 | 52.8 |

### Pass 2: einvoice.j2.typ (ZUGFeRD EN 16931)

| Concurrency | Requests | OK | 503 | Errors | p50 (ms) | p95 (ms) | p99 (ms) | Max (ms) | RPS | RSS (MB) |
|-------------|----------|----|-----|--------|----------|----------|----------|----------|-----|----------|
| 20 | 50 | 10 | 40 | 0 | 165.8 | 169.2 | 169.3 | 169.3 | 48.7 | 64.7 |
| 50 | 100 | 16 | 84 | 0 | 187.8 | 274.0 | 276.1 | 276.7 | 45.2 | 69.1 |
| 100 | 100 | 16 | 84 | 0 | 218.7 | 262.5 | 272.6 | 275.1 | 42.3 | 69.5 |

### Verdict

- **Zero errors** at all concurrency levels for both render paths.
- **Backpressure works**: 503s activate when concurrent renders exceed 8.
- **Peak RSS**: 69.5MB — memory stays bounded.
- **E-invoice overhead** at 20 concurrent: p99 169.3ms vs 168.5ms for simple invoice (1.0x).

**Architecture verdict**: Bounded, honest, acceptable for current stage. Not infinitely elastic — would need queueing/worker evolution for high-throughput service.
