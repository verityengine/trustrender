"""Soak test for Formforge — long-running repetition under mixed conditions.

Tests runtime stability over many iterations:
- Sequential library renders (no server)
- Concurrent server renders with sustained load
- Mixed success/failure (valid + invalid data interleaved)
- Memory drift tracking via RSS
- Temp artifact cleanup verification

Run library soak (no server needed):
    python benchmarks/soak_test.py --library

Run server soak (start server first):
    formforge serve --templates examples --port 8192
    python benchmarks/soak_test.py --server

Run mixed success/failure:
    python benchmarks/soak_test.py --mixed
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import resource
import statistics
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Add src to path for library imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

TEMPLATE_DIR = Path(__file__).parent.parent / "examples"
SERVER_URL = "http://127.0.0.1:8192"


def get_rss_mb() -> float:
    """Current process RSS in MB (macOS/Linux)."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # macOS reports in bytes, Linux in KB
    if sys.platform == "darwin":
        return usage.ru_maxrss / 1024 / 1024
    return usage.ru_maxrss / 1024


def count_temp_files() -> int:
    return len(glob.glob(str(TEMPLATE_DIR / "_formforge_*.typ")))


def load_data(name: str) -> dict:
    return json.loads((TEMPLATE_DIR / f"{name}_data.json").read_text())


# -----------------------------------------------------------------------
# Library soak — no server, direct render() calls
# -----------------------------------------------------------------------


def run_library_soak(iterations: int = 500) -> dict:
    """Render repeatedly via library API, track memory and timing."""
    from formforge import render

    templates = [
        ("invoice.j2.typ", "invoice"),
        ("statement.j2.typ", "statement"),
        ("receipt.j2.typ", "receipt"),
        ("letter.j2.typ", "letter"),
        ("report.j2.typ", "report"),
    ]

    # Also include long fixtures
    long_fixtures = [
        ("invoice.j2.typ", "invoice_long"),
        ("statement.j2.typ", "statement_long"),
    ]

    all_fixtures = templates + long_fixtures

    print(f"Library soak: {iterations} renders across {len(all_fixtures)} fixtures")
    print()

    rss_start = get_rss_mb()
    temp_before = count_temp_files()
    latencies = []
    errors = 0

    start = time.perf_counter()
    for i in range(iterations):
        tmpl_name, data_name = all_fixtures[i % len(all_fixtures)]
        tmpl_path = TEMPLATE_DIR / tmpl_name
        data = load_data(data_name)

        t0 = time.perf_counter()
        try:
            pdf = render(str(tmpl_path), data)
            lat = (time.perf_counter() - t0) * 1000
            latencies.append(lat)
            if not pdf[:5] == b"%PDF-":
                errors += 1
                print(f"  [{i}] Bad PDF output")
        except Exception as exc:
            errors += 1
            lat = (time.perf_counter() - t0) * 1000
            latencies.append(lat)
            if i < 5 or errors <= 3:
                print(f"  [{i}] Error: {exc}")

        # Progress every 100 iterations
        if (i + 1) % 100 == 0:
            rss_now = get_rss_mb()
            print(f"  [{i + 1}/{iterations}] RSS: {rss_now:.1f} MB, errors: {errors}")

    total = time.perf_counter() - start
    rss_end = get_rss_mb()
    temp_after = count_temp_files()

    results = {
        "type": "library",
        "iterations": iterations,
        "total_time_s": round(total, 1),
        "rps": round(iterations / total, 1),
        "errors": errors,
        "latency": _stats(latencies),
        "rss_start_mb": round(rss_start, 1),
        "rss_end_mb": round(rss_end, 1),
        "rss_drift_mb": round(rss_end - rss_start, 1),
        "temp_before": temp_before,
        "temp_after": temp_after,
    }

    _print_results(results)
    return results


# -----------------------------------------------------------------------
# Server soak — sustained concurrent load
# -----------------------------------------------------------------------


def run_server_soak(
    iterations: int = 300, workers: int = 5, burst_size: int = 10
) -> dict:
    """Sustained server load: sequential batches of concurrent requests."""
    import httpx

    data = load_data("invoice")
    long_data = load_data("invoice_long")

    print(f"Server soak: {iterations} renders, {workers} workers, burst={burst_size}")
    print(f"Server: {SERVER_URL}")
    print()

    # Health check
    with httpx.Client() as client:
        try:
            resp = client.get(f"{SERVER_URL}/health", timeout=5)
            print(f"  Health: {resp.json()}")
        except Exception as exc:
            print(f"  Server not reachable: {exc}")
            return {"error": "server not reachable"}
    print()

    temp_before = count_temp_files()
    latencies = []
    errors = 0
    batches = iterations // burst_size

    start = time.perf_counter()
    with httpx.Client() as client:
        for batch in range(batches):
            # Alternate between short and long invoice
            use_data = long_data if batch % 3 == 0 else data
            template = "invoice.j2.typ"

            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = []
                for _ in range(burst_size):
                    futures.append(
                        pool.submit(_server_render, client, template, use_data)
                    )
                for f in as_completed(futures):
                    ok, lat = f.result()
                    latencies.append(lat)
                    if not ok:
                        errors += 1

            if (batch + 1) % 10 == 0:
                elapsed = time.perf_counter() - start
                print(
                    f"  [batch {batch + 1}/{batches}] "
                    f"{len(latencies)} renders, {errors} errors, "
                    f"{elapsed:.1f}s elapsed"
                )

    total = time.perf_counter() - start
    temp_after = count_temp_files()

    results = {
        "type": "server",
        "iterations": len(latencies),
        "workers": workers,
        "burst_size": burst_size,
        "total_time_s": round(total, 1),
        "rps": round(len(latencies) / total, 1),
        "errors": errors,
        "latency": _stats(latencies),
        "temp_before": temp_before,
        "temp_after": temp_after,
    }

    _print_results(results)
    return results


def _server_render(client, template: str, data: dict) -> tuple[bool, float]:
    t0 = time.perf_counter()
    try:
        resp = client.post(
            f"{SERVER_URL}/render",
            json={"template": template, "data": data},
            timeout=30.0,
        )
        lat = (time.perf_counter() - t0) * 1000
        if resp.status_code == 200 and resp.content[:5] == b"%PDF-":
            return True, lat
        return False, lat
    except Exception:
        lat = (time.perf_counter() - t0) * 1000
        return False, lat


# -----------------------------------------------------------------------
# Mixed success/failure soak
# -----------------------------------------------------------------------


def run_mixed_soak(iterations: int = 200) -> dict:
    """Interleave valid renders, contract failures, and template errors."""
    from formforge import render
    from formforge.errors import ErrorCode, FormforgeError

    invoice_data = load_data("invoice")
    statement_data = load_data("statement")

    # Bad data variants
    bad_missing = {"invoice_number": "BAD-001"}  # Missing most fields
    bad_type = dict(invoice_data, sender="not an object")  # Wrong type
    bad_null = dict(invoice_data, subtotal=None)  # Null field

    scenarios = [
        # (template, data, validate, expected_outcome)
        ("invoice.j2.typ", invoice_data, True, "success"),
        ("invoice.j2.typ", invoice_data, False, "success"),
        ("statement.j2.typ", statement_data, False, "success"),
        ("invoice.j2.typ", bad_missing, True, "DATA_CONTRACT"),
        ("invoice.j2.typ", bad_type, True, "DATA_CONTRACT"),
        ("invoice.j2.typ", bad_null, True, "DATA_CONTRACT"),
        ("invoice.j2.typ", bad_missing, False, "TEMPLATE_VARIABLE"),
    ]

    print(f"Mixed soak: {iterations} renders (valid + contract failures + template errors)")
    print()

    rss_start = get_rss_mb()
    temp_before = count_temp_files()
    counts = {"success": 0, "DATA_CONTRACT": 0, "TEMPLATE_VARIABLE": 0, "unexpected": 0}
    latencies = []

    start = time.perf_counter()
    for i in range(iterations):
        tmpl_name, data, validate, expected = scenarios[i % len(scenarios)]
        tmpl_path = str(TEMPLATE_DIR / tmpl_name)

        t0 = time.perf_counter()
        try:
            pdf = render(tmpl_path, data, validate=validate)
            lat = (time.perf_counter() - t0) * 1000
            latencies.append(lat)
            if expected == "success":
                counts["success"] += 1
            else:
                counts["unexpected"] += 1
                print(f"  [{i}] Expected {expected}, got success")
        except FormforgeError as exc:
            lat = (time.perf_counter() - t0) * 1000
            latencies.append(lat)
            code = exc.code.value
            if code == expected:
                counts[code] += 1
            else:
                counts["unexpected"] += 1
                if counts["unexpected"] <= 3:
                    print(f"  [{i}] Expected {expected}, got {code}: {exc}")
        except Exception as exc:
            lat = (time.perf_counter() - t0) * 1000
            latencies.append(lat)
            counts["unexpected"] += 1
            if counts["unexpected"] <= 3:
                print(f"  [{i}] Unexpected exception: {exc}")

        if (i + 1) % 50 == 0:
            rss_now = get_rss_mb()
            print(f"  [{i + 1}/{iterations}] RSS: {rss_now:.1f} MB, unexpected: {counts['unexpected']}")

    total = time.perf_counter() - start
    rss_end = get_rss_mb()
    temp_after = count_temp_files()

    results = {
        "type": "mixed",
        "iterations": iterations,
        "total_time_s": round(total, 1),
        "counts": counts,
        "latency": _stats(latencies),
        "rss_start_mb": round(rss_start, 1),
        "rss_end_mb": round(rss_end, 1),
        "rss_drift_mb": round(rss_end - rss_start, 1),
        "temp_before": temp_before,
        "temp_after": temp_after,
    }

    _print_results(results)
    return results


# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------


def _stats(times: list[float]) -> dict:
    if not times:
        return {}
    times.sort()
    return {
        "count": len(times),
        "avg_ms": round(statistics.mean(times), 1),
        "p50_ms": round(times[len(times) // 2], 1),
        "p95_ms": round(times[int(len(times) * 0.95)], 1),
        "max_ms": round(max(times), 1),
        "min_ms": round(min(times), 1),
    }


def _print_results(results: dict) -> None:
    print()
    print("=" * 50)
    for k, v in results.items():
        if isinstance(v, dict):
            print(f"  {k}:")
            for kk, vv in v.items():
                print(f"    {kk}: {vv}")
        else:
            print(f"  {k}: {v}")
    print("=" * 50)
    print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Formforge soak test")
    parser.add_argument("--library", action="store_true", help="Library render soak (no server)")
    parser.add_argument("--server", action="store_true", help="Server concurrent soak")
    parser.add_argument("--mixed", action="store_true", help="Mixed success/failure soak")
    parser.add_argument("-n", type=int, default=None, help="Override iteration count")
    args = parser.parse_args()

    if not any([args.library, args.server, args.mixed]):
        args.library = True
        args.mixed = True

    if args.library:
        run_library_soak(iterations=args.n or 500)

    if args.mixed:
        run_mixed_soak(iterations=args.n or 200)

    if args.server:
        run_server_soak(iterations=args.n or 300)
