"""Large-document pagination soak test.

Measures render performance for documents with hundreds to thousands of rows.
Tracks render time, peak RSS, page count, output file size, and time-per-row.

Usage:
    python benchmarks/pagination_soak.py
"""

from __future__ import annotations

import io
import json
import resource
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import os  # noqa: E402
os.environ["FORMFORGE_BACKEND"] = "typst-cli"  # production backend

import formforge  # noqa: E402
from pypdf import PdfReader  # noqa: E402

EXAMPLES = Path(__file__).parent.parent / "examples"
RESULTS_FILE = Path(__file__).parent / "pagination_soak_results.md"

# Test matrix: (label, template, data_file, row_count, iterations)
MATRIX = [
    ("invoice-50", "invoice.j2.typ", "invoice_long_data.json", 50, 20),
    ("invoice-1000", "invoice.j2.typ", "invoice_1000_data.json", 1000, 10),
    ("statement-201", "statement.j2.typ", "statement_long_data.json", 201, 20),
    ("statement-1000", "statement.j2.typ", "statement_1000_data.json", 1000, 10),
    ("report-dense", "report.j2.typ", "report_long_data.json", 115, 20),
]


def get_rss_mb() -> float:
    """Current process peak RSS in MB."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    if sys.platform == "darwin":
        return usage.ru_maxrss / 1024 / 1024
    return usage.ru_maxrss / 1024


def percentile(data: list[float], p: int) -> float:
    """Calculate percentile from sorted data."""
    sorted_data = sorted(data)
    k = (len(sorted_data) - 1) * p / 100
    f = int(k)
    c = f + 1
    if c >= len(sorted_data):
        return sorted_data[f]
    return sorted_data[f] + (k - f) * (sorted_data[c] - sorted_data[f])


def run_fixture(label: str, template: str, data_file: str, row_count: int, iterations: int) -> dict:
    """Run a single fixture through multiple render iterations."""
    template_path = str(EXAMPLES / template)
    data = json.loads((EXAMPLES / data_file).read_text(encoding="utf-8"))

    timings = []
    page_count = 0
    file_size = 0

    for i in range(iterations):
        start = time.perf_counter()
        pdf_bytes = formforge.render(template_path, data, validate=False)
        elapsed = time.perf_counter() - start
        timings.append(elapsed * 1000)  # ms

        # Extract page count and file size on first iteration only
        if i == 0:
            reader = PdfReader(io.BytesIO(pdf_bytes))
            page_count = len(reader.pages)
            file_size = len(pdf_bytes)

    rss = get_rss_mb()

    return {
        "label": label,
        "rows": row_count,
        "pages": page_count,
        "file_size_kb": round(file_size / 1024),
        "iterations": iterations,
        "p50_ms": round(percentile(timings, 50), 1),
        "p95_ms": round(percentile(timings, 95), 1),
        "p99_ms": round(percentile(timings, 99), 1),
        "max_ms": round(max(timings), 1),
        "min_ms": round(min(timings), 1),
        "avg_ms": round(statistics.mean(timings), 1),
        "ms_per_row": round(statistics.mean(timings) / row_count, 2),
        "rss_mb": round(rss, 1),
    }


def main():
    print("Pagination soak test")
    print("=" * 60)

    rss_start = get_rss_mb()
    results = []

    for label, template, data_file, row_count, iterations in MATRIX:
        print(f"\n  {label}: {iterations} iterations...", end=" ", flush=True)
        result = run_fixture(label, template, data_file, row_count, iterations)
        results.append(result)
        print(f"{result['pages']} pages, p50={result['p50_ms']}ms, p95={result['p95_ms']}ms")

    rss_end = get_rss_mb()

    # Write results
    lines = [
        "# Pagination Soak Results",
        "",
        f"Date: {time.strftime('%Y-%m-%d %H:%M')}",
        f"Platform: {sys.platform}, Python {sys.version.split()[0]}",
        f"Backend: typst-cli (subprocess, production server path)",
        f"RSS start: {rss_start:.1f} MB, RSS end: {rss_end:.1f} MB",
        "",
        "## Render Performance",
        "",
        "| Fixture | Rows | Pages | Size | Iters | P50 | P95 | P99 | Max | ms/row |",
        "|---------|------|-------|------|-------|-----|-----|-----|-----|--------|",
    ]

    for r in results:
        lines.append(
            f"| {r['label']} | {r['rows']} | {r['pages']} | {r['file_size_kb']} KB "
            f"| {r['iterations']} | {r['p50_ms']} ms | {r['p95_ms']} ms "
            f"| {r['p99_ms']} ms | {r['max_ms']} ms | {r['ms_per_row']} |"
        )

    lines.extend([
        "",
        "## Observations",
        "",
        "Numbers above are measured, not targets.",
    ])

    report = "\n".join(lines) + "\n"
    RESULTS_FILE.write_text(report, encoding="utf-8")
    print(f"\nResults written to {RESULTS_FILE}")

    # Print summary
    print("\n" + "=" * 60)
    print("Summary:")
    for r in results:
        print(f"  {r['label']:20s}  {r['rows']:>5} rows  {r['pages']:>3} pages  "
              f"p50={r['p50_ms']:>7.1f}ms  p95={r['p95_ms']:>7.1f}ms  "
              f"ms/row={r['ms_per_row']:.2f}")
    print(f"\n  RSS: {rss_start:.1f} MB -> {rss_end:.1f} MB (delta: {rss_end - rss_start:+.1f} MB)")
    print(f"  Total renders: {sum(r['iterations'] for r in results)}")
    print(f"  Zero errors.")


if __name__ == "__main__":
    main()
