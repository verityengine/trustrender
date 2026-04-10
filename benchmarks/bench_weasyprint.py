"""Benchmark WeasyPrint rendering for comparison against Typst."""

import os
import resource
import time

from weasyprint import HTML


def bench_weasyprint(html_path, n=100):
    """Benchmark WeasyPrint rendering."""
    # Cold
    start = time.perf_counter()
    HTML(filename=html_path).write_pdf()
    cold = time.perf_counter() - start

    # Warm (n iterations)
    times = []
    for _ in range(n):
        start = time.perf_counter()
        HTML(filename=html_path).write_pdf()
        times.append(time.perf_counter() - start)

    return cold, times


def stats(times):
    avg = sum(times) / len(times)
    mn = min(times)
    mx = max(times)
    p50 = sorted(times)[len(times) // 2]
    return avg, mn, mx, p50


def get_memory_mb():
    usage = resource.getrusage(resource.RUSAGE_SELF)
    if os.uname().sysname == "Darwin":
        return usage.ru_maxrss / (1024 * 1024)
    return usage.ru_maxrss / 1024


if __name__ == "__main__":
    N = 100

    print("=" * 60)
    print("WEASYPRINT BENCHMARK")
    print("=" * 60)
    print(f"Iterations: {N}")
    print()

    html_path = "benchmarks/invoice_weasyprint.html"

    print("--- Simple Invoice (HTML, 1 page) ---")
    cold, times = bench_weasyprint(html_path, N)
    avg, mn, mx, p50 = stats(times)
    print(f"  Cold:   {cold*1000:>8.1f}ms")
    print(f"  Avg:    {avg*1000:>8.1f}ms")
    print(f"  Median: {p50*1000:>8.1f}ms")
    print(f"  Min:    {mn*1000:>8.1f}ms")
    print(f"  Max:    {mx*1000:>8.1f}ms")
    print()

    # Check output size
    pdf_bytes = HTML(filename=html_path).write_pdf()
    print(f"  PDF size: {len(pdf_bytes):,} bytes")
    print()

    peak_mb = get_memory_mb()
    print(f"--- Memory ---")
    print(f"  Peak RSS: {peak_mb:.1f} MB")
    print()
    print("=" * 60)
