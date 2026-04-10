"""Benchmark Typst rendering: cold, warm, and throughput."""

import json
import os
import resource
import time

from jinja2 import Environment, FileSystemLoader
import typst


def _typst_escape(value):
    if not isinstance(value, str):
        return value
    s = value
    for char in ("\\", "$", "#", "@"):
        s = s.replace(char, "\\" + char)
    return s


def setup_jinja_env():
    return Environment(
        loader=FileSystemLoader("examples"),
        finalize=_typst_escape,
    )


def render_jinja_to_file(env, data, template_name="_rendered.typ"):
    """Render Jinja2 template to a temp .typ file, return path."""
    template = env.get_template("invoice.j2.typ")
    rendered = template.render(**data)
    path = os.path.join("examples", template_name)
    with open(path, "w") as f:
        f.write(rendered)
    return path


def bench_static_compile(typ_file, n=100):
    """Benchmark compiling a static .typ file."""
    # Cold
    start = time.perf_counter()
    typst.compile(typ_file, format="pdf")
    cold = time.perf_counter() - start

    # Warm (n iterations)
    times = []
    for _ in range(n):
        start = time.perf_counter()
        typst.compile(typ_file, format="pdf")
        times.append(time.perf_counter() - start)

    return cold, times


def bench_jinja_pipeline(data_path, n=100):
    """Benchmark full Jinja2 -> Typst pipeline."""
    with open(data_path) as f:
        data = json.load(f)

    env = setup_jinja_env()

    # Cold (first render)
    start = time.perf_counter()
    tmp = render_jinja_to_file(env, data)
    typst.compile(tmp, format="pdf")
    cold = time.perf_counter() - start

    # Warm (n iterations)
    times = []
    for _ in range(n):
        start = time.perf_counter()
        tmp = render_jinja_to_file(env, data)
        typst.compile(tmp, format="pdf")
        times.append(time.perf_counter() - start)

    # Cleanup
    if os.path.exists(tmp):
        os.remove(tmp)

    return cold, times


def get_memory_mb():
    """Get peak RSS in MB (macOS/Linux)."""
    usage = resource.getrusage(resource.RUSAGE_SELF)
    # macOS reports in bytes, Linux in KB
    if os.uname().sysname == "Darwin":
        return usage.ru_maxrss / (1024 * 1024)
    return usage.ru_maxrss / 1024


def stats(times):
    avg = sum(times) / len(times)
    mn = min(times)
    mx = max(times)
    p50 = sorted(times)[len(times) // 2]
    return avg, mn, mx, p50


if __name__ == "__main__":
    N = 100

    print("=" * 60)
    print("TYPST BENCHMARK")
    print("=" * 60)
    print(f"Iterations: {N}")
    print()

    # --- Simple invoice (static) ---
    print("--- Simple Invoice (static .typ, 1 page) ---")
    cold, times = bench_static_compile("examples/invoice_simple.typ", N)
    avg, mn, mx, p50 = stats(times)
    print(f"  Cold:   {cold*1000:>8.1f}ms")
    print(f"  Avg:    {avg*1000:>8.1f}ms")
    print(f"  Median: {p50*1000:>8.1f}ms")
    print(f"  Min:    {mn*1000:>8.1f}ms")
    print(f"  Max:    {mx*1000:>8.1f}ms")
    print()

    # --- Multi-page invoice (static) ---
    print("--- Multi-page Invoice (static .typ, 3 pages) ---")
    cold, times = bench_static_compile("examples/invoice_multipage.typ", N)
    avg, mn, mx, p50 = stats(times)
    print(f"  Cold:   {cold*1000:>8.1f}ms")
    print(f"  Avg:    {avg*1000:>8.1f}ms")
    print(f"  Median: {p50*1000:>8.1f}ms")
    print(f"  Min:    {mn*1000:>8.1f}ms")
    print(f"  Max:    {mx*1000:>8.1f}ms")
    print()

    # --- Jinja2 pipeline ---
    print("--- Jinja2 Pipeline (JSON -> Jinja2 -> Typst -> PDF, 1 page) ---")
    cold, times = bench_jinja_pipeline("examples/invoice_data.json", N)
    avg, mn, mx, p50 = stats(times)
    print(f"  Cold:   {cold*1000:>8.1f}ms")
    print(f"  Avg:    {avg*1000:>8.1f}ms")
    print(f"  Median: {p50*1000:>8.1f}ms")
    print(f"  Min:    {mn*1000:>8.1f}ms")
    print(f"  Max:    {mx*1000:>8.1f}ms")
    print()

    # --- Memory ---
    peak_mb = get_memory_mb()
    print(f"--- Memory ---")
    print(f"  Peak RSS: {peak_mb:.1f} MB")
    print()

    # --- Dependency footprint ---
    typst_pkg = os.path.dirname(typst.__file__)
    typst_size = sum(
        os.path.getsize(os.path.join(dp, f))
        for dp, _, fns in os.walk(typst_pkg)
        for f in fns
    )
    print(f"--- Dependency Footprint ---")
    print(f"  typst package: {typst_size / (1024*1024):.1f} MB")
    print()
    print("=" * 60)
