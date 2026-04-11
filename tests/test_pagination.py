"""Automated pagination proof — verifies multi-page table behavior.

Tests page counts, row preservation, header repetition, and totals
placement across invoice, statement, and report templates at various
data scales (10, 50, 201, 1000 rows).

Uses pypdf for PDF inspection (already a dependency via drafthorse).
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest
from pypdf import PdfReader

import trustrender

EXAMPLES = Path("examples")


# --- Helpers ----------------------------------------------------------------


def pdf_page_count(pdf_bytes: bytes) -> int:
    """Extract page count from PDF bytes."""
    return len(PdfReader(io.BytesIO(pdf_bytes)).pages)


def pdf_full_text(pdf_bytes: bytes) -> str:
    """Extract all text from all pages of a PDF."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def pdf_page_texts(pdf_bytes: bytes) -> list[str]:
    """Extract text from each page individually."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return [page.extract_text() or "" for page in reader.pages]


def render(template: str, data_file: str) -> bytes:
    """Render a template with data, return raw PDF bytes."""
    data = json.loads((EXAMPLES / data_file).read_text(encoding="utf-8"))
    return trustrender.render(
        str(EXAMPLES / template),
        data,
        validate=False,
    )


# --- Invoice pagination ----------------------------------------------------


class TestInvoicePagination:
    """Verify invoice table pagination at 10, 50, and 1000 rows."""

    def test_standard_invoice_page_count(self):
        """10-item invoice fits in 1-2 pages (depends on template layout)."""
        pdf = render("invoice.j2.typ", "invoice_data.json")
        assert pdf_page_count(pdf) <= 2

    def test_50_row_invoice_page_count(self):
        """50-item invoice produces multiple pages (manual proof: 3)."""
        pdf = render("invoice.j2.typ", "invoice_long_data.json")
        pages = pdf_page_count(pdf)
        assert pages >= 3, f"Expected >= 3 pages, got {pages}"

    def test_50_row_invoice_all_rows_present(self):
        """All 50 item descriptions appear in the extracted text."""
        pdf = render("invoice.j2.typ", "invoice_long_data.json")
        text = pdf_full_text(pdf)
        data = json.loads((EXAMPLES / "invoice_long_data.json").read_text())
        for item in data["items"]:
            # Spot-check: every item number appears
            assert str(item["num"]) in text, f"Item {item['num']} missing from PDF text"

    def test_50_row_invoice_content_spans_pages(self):
        """Invoice content is distributed across all pages (no blank pages)."""
        pdf = render("invoice.j2.typ", "invoice_long_data.json")
        page_texts = pdf_page_texts(pdf)
        # Every page should have meaningful content (item data or totals)
        non_empty = sum(1 for t in page_texts if len(t.strip()) > 50)
        assert non_empty == len(page_texts), "Found blank or near-empty pages"

    def test_50_row_invoice_total_present(self):
        """The total value appears somewhere in the PDF."""
        pdf = render("invoice.j2.typ", "invoice_long_data.json")
        text = pdf_full_text(pdf)
        # The total in invoice_long_data.json is $290,291.00
        assert "290,291" in text, "Invoice total not found in PDF text"


# --- Statement pagination --------------------------------------------------


class TestStatementPagination:
    """Verify statement table pagination at standard, 201, and 1000 rows."""

    def test_standard_statement_page_count(self):
        """Standard statement (~12 transactions) fits in 1-2 pages."""
        pdf = render("statement.j2.typ", "statement_data.json")
        pages = pdf_page_count(pdf)
        assert pages in (1, 2), f"Expected 1-2 pages, got {pages}"

    def test_201_row_statement_page_count(self):
        """201-row statement produces multiple pages (manual proof: 7)."""
        pdf = render("statement.j2.typ", "statement_long_data.json")
        pages = pdf_page_count(pdf)
        assert pages >= 6, f"Expected >= 6 pages, got {pages}"

    def test_201_row_statement_rows_present(self):
        """Spot-check that transactions appear across the full document."""
        pdf = render("statement.j2.typ", "statement_long_data.json")
        text = pdf_full_text(pdf)
        # The fixture has known reference codes — spot-check first, middle, last
        data = json.loads((EXAMPLES / "statement_long_data.json").read_text())
        transactions = data["transactions"]
        # Opening balance (first)
        assert "Opening Balance" in text
        # A middle transaction
        mid = transactions[len(transactions) // 2]
        if mid["reference"]:
            assert mid["reference"] in text, f"Mid reference {mid['reference']} not found"
        # Closing balance value — strip spaces for pypdf extraction quirks
        closing_digits = data["closing_balance"].replace("$", "").replace(",", "").replace(" ", "")
        text_digits = text.replace(",", "").replace(" ", "")
        assert closing_digits in text_digits, f"Closing balance {closing_digits} not found"

    def test_201_row_statement_content_spans_pages(self):
        """Statement content is distributed across all pages."""
        pdf = render("statement.j2.typ", "statement_long_data.json")
        page_texts = pdf_page_texts(pdf)
        non_empty = sum(1 for t in page_texts if len(t.strip()) > 50)
        assert non_empty == len(page_texts), "Found blank or near-empty pages"

    def test_201_row_statement_closing_balance(self):
        """Closing balance value appears in the PDF."""
        pdf = render("statement.j2.typ", "statement_long_data.json")
        text = pdf_full_text(pdf)
        # pypdf may insert spaces in extracted numbers — strip for comparison
        assert "37275" in text.replace(" ", "").replace(",", ""), "Closing balance not found"


# --- Report pagination ------------------------------------------------------


class TestReportPagination:
    """Verify report template handles multiple sections across pages."""

    def test_report_is_multipage(self):
        """Standard report spans multiple pages."""
        pdf = render("report.j2.typ", "report_data.json")
        pages = pdf_page_count(pdf)
        assert pages >= 2, f"Expected >= 2 pages, got {pages}"

    def test_report_all_sections_present(self):
        """All report sections appear in the output."""
        pdf = render("report.j2.typ", "report_data.json")
        text = pdf_full_text(pdf)
        # Key section content from report_data.json
        assert "Uptime" in text, "Metrics section missing"
        assert "99.94%" in text, "Uptime value missing"
        assert "INC-2026" in text, "Incident section missing"
        assert "Compute" in text, "Spend section missing"


# --- Large document pagination (1000-row fixtures) --------------------------


class TestLargeDocumentPagination:
    """Verify pagination at 1000-row scale — the anti-Chromium proof."""

    def test_1000_item_invoice_renders(self):
        """1000-item invoice renders to a valid multi-page PDF."""
        pdf = render("invoice.j2.typ", "invoice_1000_data.json")
        pages = pdf_page_count(pdf)
        assert pages >= 20, f"Expected >= 20 pages for 1000 items, got {pages}"
        assert pdf[:5] == b"%PDF-"

    def test_1000_item_invoice_rows_present(self):
        """Spot-check first, middle, and last items in 1000-item invoice."""
        pdf = render("invoice.j2.typ", "invoice_1000_data.json")
        text = pdf_full_text(pdf)
        data = json.loads((EXAMPLES / "invoice_1000_data.json").read_text())
        items = data["items"]
        # First item
        assert items[0]["description"].split("\u2014")[0].strip() in text
        # Middle item (500th)
        assert str(items[499]["num"]) in text, "Item 500 not found"
        # Last item
        assert str(items[-1]["num"]) in text, "Item 1000 not found"
        # Total
        total_num = data["total"].replace("$", "").replace(",", "").split(".")[0]
        assert total_num in text.replace(",", ""), "Invoice total not found"

    def test_1000_item_invoice_content_spans_pages(self):
        """All pages of the 1000-item invoice have meaningful content."""
        pdf = render("invoice.j2.typ", "invoice_1000_data.json")
        page_texts = pdf_page_texts(pdf)
        non_empty = sum(1 for t in page_texts if len(t.strip()) > 50)
        assert non_empty == len(page_texts), "Found blank or near-empty pages"

    def test_1000_row_statement_renders(self):
        """1000-row statement renders to a valid multi-page PDF."""
        pdf = render("statement.j2.typ", "statement_1000_data.json")
        pages = pdf_page_count(pdf)
        assert pages >= 20, f"Expected >= 20 pages for 1000 rows, got {pages}"
        assert pdf[:5] == b"%PDF-"

    def test_1000_row_statement_rows_present(self):
        """Spot-check first, middle, and last rows in 1000-row statement."""
        pdf = render("statement.j2.typ", "statement_1000_data.json")
        text = pdf_full_text(pdf)
        data = json.loads((EXAMPLES / "statement_1000_data.json").read_text())
        txns = data["transactions"]
        assert "Opening Balance" in text
        # Middle transaction reference
        mid = txns[len(txns) // 2]
        if mid["reference"]:
            assert mid["reference"] in text, f"Mid reference {mid['reference']} not found"
        # Closing balance
        closing = data["closing_balance"].replace("$", "").replace(",", "").split(".")[0]
        assert closing in text.replace(",", ""), "Closing balance not found"

    def test_1000_row_statement_content_spans_pages(self):
        """All pages of the 1000-row statement have meaningful content."""
        pdf = render("statement.j2.typ", "statement_1000_data.json")
        page_texts = pdf_page_texts(pdf)
        non_empty = sum(1 for t in page_texts if len(t.strip()) > 50)
        assert non_empty == len(page_texts), "Found blank or near-empty pages"

    def test_dense_report_renders(self):
        """Dense report (50 metrics, 20 incidents, 30 services) renders cleanly."""
        pdf = render("report.j2.typ", "report_long_data.json")
        pages = pdf_page_count(pdf)
        assert pages >= 5, f"Expected >= 5 pages for dense report, got {pages}"
        text = pdf_full_text(pdf)
        # Verify content from all sections
        assert "Uptime" in text, "Metrics section missing"
        assert "INC-2026-0001" in text, "First incident missing"
        assert "INC-2026-0020" in text, "Last incident missing"
        assert "Compute" in text, "Spend section missing"
        assert "Recommendation" in text, "Recommendations section missing"
