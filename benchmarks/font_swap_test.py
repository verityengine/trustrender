"""Font-swap reproducibility test.

Tests whether silent font fallback produces different output,
and whether existing drift detection fields would catch it.

Usage:
    python benchmarks/font_swap_test.py
"""

import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from trustrender import render, bundled_font_dir
from trustrender.doctor import check_template_fonts


EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
INVOICE_DATA = json.loads((EXAMPLES / "invoice_data.json").read_text())
TEMPLATE = str(EXAMPLES / "invoice.j2.typ")


def _count_pages(pdf_bytes: bytes) -> int | None:
    """Count PDF pages from raw bytes."""
    try:
        import pypdf
        import io
        reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
        return len(reader.pages)
    except ImportError:
        # Fallback: count /Type /Page occurrences
        count = pdf_bytes.count(b"/Type /Page")
        # Subtract catalog pages
        return max(1, count - pdf_bytes.count(b"/Type /Pages"))


def main():
    print("Font-Swap Drift Detection Test")
    print("=" * 60)

    fonts_dir = bundled_font_dir()
    print(f"Bundled fonts: {fonts_dir}")

    # 1. Doctor font check
    print("\n--- Doctor font check ---")
    status, msg = check_template_fonts()
    print(f"  [{status}] {msg}")

    # 2. Render with correct fonts (bundled Inter)
    print("\n--- Render with bundled Inter fonts ---")
    correct_bytes = render(TEMPLATE, INVOICE_DATA)
    correct_size = len(correct_bytes)
    correct_pages = _count_pages(correct_bytes)
    print(f"  PDF size: {correct_size} bytes")
    print(f"  Pages: {correct_pages}")

    # 3. Render with empty font path (force Typst system fallback)
    print("\n--- Render with empty font path (force fallback) ---")
    with tempfile.TemporaryDirectory() as empty_font_dir:
        fallback_bytes = render(
            TEMPLATE,
            INVOICE_DATA,
            font_paths=[empty_font_dir],
        )
    fallback_size = len(fallback_bytes)
    fallback_pages = _count_pages(fallback_bytes)
    print(f"  PDF size: {fallback_size} bytes")
    print(f"  Pages: {fallback_pages}")
    print(f"  Render succeeded silently: YES (no error raised)")

    # 4. Comparison
    size_diff = abs(correct_size - fallback_size)
    size_ratio = fallback_size / correct_size if correct_size > 0 else 0
    size_change_pct = abs(1 - size_ratio) * 100
    bytes_identical = correct_bytes == fallback_bytes
    page_count_changed = correct_pages != fallback_pages

    print(f"\n--- Comparison ---")
    print(f"  Bytes identical:     {bytes_identical}")
    print(f"  Size difference:     {size_diff} bytes ({size_change_pct:.1f}%)")
    print(f"  Page count changed:  {page_count_changed} ({correct_pages} -> {fallback_pages})")

    # 5. Would drift detection catch it?
    print(f"\n--- Drift detection analysis ---")

    # Drift checks: page count change, file size change (>20% = warning, >50% = error)
    would_catch_page = page_count_changed
    would_catch_size_warn = size_change_pct > 20
    would_catch_size_error = size_change_pct > 50

    print(f"  Page count drift:   {'WOULD CATCH' if would_catch_page else 'WOULD MISS'}")
    print(f"  Size drift (>20%):  {'WOULD CATCH (warning)' if would_catch_size_warn else 'WOULD MISS'}")
    print(f"  Size drift (>50%):  {'WOULD CATCH (error)' if would_catch_size_error else 'WOULD MISS'}")

    # 6. Verdict
    print(f"\n--- Verdict ---")
    font_changed = not bytes_identical

    if not font_changed:
        print("  INCONCLUSIVE: Font swap did not change output.")
        print("  System may have Inter installed as a system font.")
        print("  To get a decisive result, test on a system without Inter.")
    elif font_changed and not would_catch_page and not would_catch_size_warn:
        print("  GAP CONFIRMED: Font swap changed output silently.")
        print("  Drift detection would NOT catch it (page count same, size change < 20%).")
        print("  Font fallback is a REAL trust gap, not just documented annoyance.")
    elif font_changed and (would_catch_page or would_catch_size_warn):
        print("  PARTIAL: Font swap changed output and drift WOULD catch it")
        print(f"  via {'page count' if would_catch_page else 'size'} change.")
        print("  But drift detection is not guaranteed to catch all font swaps.")

    # Write results
    out_path = Path(__file__).parent / "font_swap_results.md"
    with open(out_path, "w") as f:
        f.write("# Font-Swap Drift Detection Results\n\n")
        f.write(f"Template: invoice.j2.typ\n")
        f.write(f"Correct font: Inter (bundled)\n")
        f.write(f"Fallback: Typst system default\n\n")
        f.write(f"| Metric | Correct | Fallback | Changed? |\n")
        f.write(f"|--------|---------|----------|----------|\n")
        f.write(f"| PDF size | {correct_size} | {fallback_size} | {size_diff} bytes ({size_change_pct:.1f}%) |\n")
        f.write(f"| Pages | {correct_pages} | {fallback_pages} | {'Yes' if page_count_changed else 'No'} |\n")
        f.write(f"| Bytes identical | — | — | {'Yes' if bytes_identical else 'No'} |\n")
        f.write(f"| Render error | No | No | — |\n\n")
        f.write(f"**Drift detection would catch:** ")
        if would_catch_page:
            f.write("Yes (page count change). ")
        elif would_catch_size_warn:
            f.write("Yes (size change > 20%). ")
        else:
            f.write("No — page count same and size change < 20%. ")
        f.write("\n")

    print(f"\nResults written to {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
