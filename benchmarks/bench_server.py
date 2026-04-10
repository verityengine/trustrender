"""Concurrent load test for the Formforge server.

Exploratory operational benchmark — not definitive capacity planning.
Tests render throughput, latency, and temp file cleanup under load.
"""

import glob
import json
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import httpx

SERVER_URL = "http://127.0.0.1:8192"
TEMPLATE_DIR = "examples"


def load_invoice_data():
    with open("examples/invoice_data.json") as f:
        return json.load(f)


def render_request(client, data, template="invoice.j2.typ"):
    """Send a single render request and return (success, latency_ms)."""
    start = time.perf_counter()
    try:
        resp = client.post(
            f"{SERVER_URL}/render",
            json={"template": template, "data": data},
            timeout=30.0,
        )
        latency = (time.perf_counter() - start) * 1000
        if resp.status_code == 200 and resp.content[:5] == b"%PDF-":
            return True, latency
        return False, latency
    except Exception as exc:
        latency = (time.perf_counter() - start) * 1000
        print(f"  Error: {exc}")
        return False, latency


def count_temp_files():
    return len(glob.glob(f"{TEMPLATE_DIR}/_formforge_*.typ"))


def stats_summary(times):
    if not times:
        return {}
    times.sort()
    return {
        "count": len(times),
        "avg_ms": f"{statistics.mean(times):.1f}",
        "p50_ms": f"{times[len(times) // 2]:.1f}",
        "p95_ms": f"{times[int(len(times) * 0.95)]:.1f}",
        "max_ms": f"{max(times):.1f}",
        "min_ms": f"{min(times):.1f}",
    }


if __name__ == "__main__":
    data = load_invoice_data()

    print("=" * 60)
    print("FORMFORGE SERVER LOAD TEST")
    print("=" * 60)
    print(f"Server: {SERVER_URL}")
    print()

    # Health check
    with httpx.Client() as client:
        resp = client.get(f"{SERVER_URL}/health")
        print(f"Health: {resp.json()}")
    print()

    # --- Sequential throughput ---
    print("--- Sequential: 50 renders ---")
    temp_before = count_temp_files()
    latencies = []
    with httpx.Client() as client:
        start = time.perf_counter()
        for i in range(50):
            ok, lat = render_request(client, data)
            if not ok:
                print(f"  FAIL at request {i}")
            latencies.append(lat)
        total = time.perf_counter() - start

    temp_after = count_temp_files()
    print(f"  Total time: {total:.1f}s")
    print(f"  RPS: {50 / total:.1f}")
    print(f"  Stats: {stats_summary(latencies)}")
    print(f"  Temp files before: {temp_before}, after: {temp_after}")
    print()

    # --- Concurrent: 10 parallel ---
    print("--- Concurrent: 10 parallel renders ---")
    temp_before = count_temp_files()
    latencies = []
    errors = 0
    with httpx.Client() as client:
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=10) as pool:
            futures = [
                pool.submit(render_request, client, data)
                for _ in range(10)
            ]
            for f in as_completed(futures):
                ok, lat = f.result()
                if not ok:
                    errors += 1
                latencies.append(lat)
        total = time.perf_counter() - start

    temp_after = count_temp_files()
    print(f"  Total time: {total:.1f}s")
    print(f"  Errors: {errors}")
    print(f"  Stats: {stats_summary(latencies)}")
    print(f"  Temp files before: {temp_before}, after: {temp_after}")
    print()

    # --- Concurrent burst: 30 parallel ---
    print("--- Concurrent burst: 30 parallel renders ---")
    temp_before = count_temp_files()
    latencies = []
    errors = 0
    with httpx.Client() as client:
        start = time.perf_counter()
        with ThreadPoolExecutor(max_workers=30) as pool:
            futures = [
                pool.submit(render_request, client, data)
                for _ in range(30)
            ]
            for f in as_completed(futures):
                ok, lat = f.result()
                if not ok:
                    errors += 1
                latencies.append(lat)
        total = time.perf_counter() - start

    temp_after = count_temp_files()
    print(f"  Total time: {total:.1f}s")
    print(f"  Errors: {errors}")
    print(f"  Stats: {stats_summary(latencies)}")
    print(f"  Temp files before: {temp_before}, after: {temp_after}")
    print()

    print("=" * 60)
