"""End-to-end render test: JSON -> Jinja2 -> Typst -> PDF"""

import json
import os
import time

from jinja2 import Environment, FileSystemLoader
import typst


def _typst_escape(value: str) -> str:
    """Escape characters that have special meaning in Typst markup."""
    s = str(value)
    # $ = math mode, # = code prefix, @ = reference, _ = emphasis
    for char in ("\\", "$", "#", "@"):
        s = s.replace(char, "\\" + char)
    return s


def render_jinja_invoice(data_path: str, template_path: str, output_path: str) -> float:
    """Render an invoice using Jinja2 preprocessing + Typst compilation.

    Returns wall-clock time in seconds.
    """
    start = time.perf_counter()

    # Load data
    with open(data_path) as f:
        data = json.load(f)

    # Jinja2 render
    template_dir = os.path.dirname(template_path)
    template_name = os.path.basename(template_path)
    env = Environment(
        loader=FileSystemLoader(template_dir),
        # Auto-escape Typst-special characters in all rendered values
        finalize=lambda x: _typst_escape(x) if isinstance(x, str) else x,
    )
    template = env.get_template(template_name)
    rendered_typ = template.render(**data)

    # Write intermediate .typ file next to the template (so relative paths work)
    intermediate = os.path.join(template_dir, "_rendered.typ")
    with open(intermediate, "w") as f:
        f.write(rendered_typ)

    # Typst compile
    typst.compile(intermediate, output=output_path)

    # Clean up intermediate
    os.remove(intermediate)

    elapsed = time.perf_counter() - start
    return elapsed


if __name__ == "__main__":
    data_path = "examples/invoice_data.json"
    template_path = "examples/invoice.j2.typ"
    output_path = "examples/output/invoice_jinja.pdf"

    elapsed = render_jinja_invoice(data_path, template_path, output_path)
    size = os.path.getsize(output_path)

    print(f"Jinja2 + Typst render: SUCCESS")
    print(f"  Time: {elapsed * 1000:.1f}ms")
    print(f"  Output: {output_path} ({size:,} bytes)")

    # Second render to show warm timing
    elapsed2 = render_jinja_invoice(data_path, template_path, output_path)
    print(f"  Warm render: {elapsed2 * 1000:.1f}ms")
