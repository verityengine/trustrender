"""End-to-end: raw Stripe → TrustRender → drafthorse → Factur-X PDF.

Proves the full chain works. Produces invoice_facturx.pdf — a real PDF/A-3b
document with embedded EN 16931 CII XML, ready for German B2B e-invoicing.

What each library does in this pipeline:
  - TrustRender:  adapt + validate the source payload, give you a canonical dict
  - You:          add the regulatory metadata TrustRender doesn't compute
                  (seller VAT ID, payment IBAN, per-line tax rates, tax entries)
  - drafthorse:   turn the enriched dict into UN/CEFACT CII XML
  - factur-x:     embed the XML into a PDF/A-3b container

Requires: pip install trustrender fpdf2

Run: python examples/with_drafthorse_facturx.py
"""

from pathlib import Path

from fpdf import FPDF

from trustrender import validate_invoice
from trustrender.adapters import from_stripe
from trustrender.zugferd import apply_zugferd, build_invoice_xml

# ── Step 1: Raw Stripe API response ──────────────────────────────────
# Pretend we just pulled this from stripe.Invoice.retrieve("in_...")

stripe_invoice = {
    "number": "INV-2026-0187",
    "currency": "eur",
    "created": 1775779200,  # 2026-04-10
    "due_date": 1778371200,  # 2026-05-10
    "subtotal": 247500,  # cents
    "tax": 47025,
    "total": 294525,
    "customer_name": "Rheingold Maschinenbau GmbH",
    "customer_email": "einkauf@rheingold-maschinenbau.de",
    "customer_address": {
        "line1": "Industriestr. 42",
        "city": "Stuttgart",
        "postal_code": "70173",
        "country": "DE",
    },
    "lines": {
        "data": [
            {"description": "Cloud infrastructure (Q2 2026)", "quantity": 1, "amount": 189000, "price": {"unit_amount": 189000}},
            {"description": "Premium support plan", "quantity": 1, "amount": 45000, "price": {"unit_amount": 45000}},
            {"description": "Data egress overage (2.1 TB)", "quantity": 1, "amount": 13500, "price": {"unit_amount": 13500}},
        ],
    },
    # Stripe doesn't include sender info — we add it before validation
    "sender": {"name": "NovaTech Solutions GmbH"},
}

print("Step 1: Adapt + validate via TrustRender")
adapted = from_stripe(stripe_invoice)
adapted["tax_rate"] = 19  # German MwSt — Stripe doesn't include this
result = validate_invoice(adapted)

assert result["render_ready"], f"Validation failed: {result['errors']}"
print(f"  → status={result['status']}, render_ready={result['render_ready']}")
canonical = result["canonical"]


# ── Step 2: Add the regulatory metadata Stripe doesn't ship ──────────
# TrustRender canonical is data-shape correct. For ZUGFeRD/Factur-X you
# also need: seller VAT ID, payment details, per-line tax_rate, tax_entries.
# In a real integration these come from your billing setup, not from Stripe.

zugferd_data = {
    **canonical,
    "seller": {
        "name": "NovaTech Solutions GmbH",
        "address": "Hauptstr. 5",
        "city": "Berlin",
        "postal_code": "10115",
        "country": "DE",
        "vat_id": "DE123456789",
        "email": "billing@novatech.example",
    },
    "buyer": {
        "name": canonical["recipient"]["name"],
        "address": "Industriestr. 42",
        "city": canonical["extras"]["recipient.city"],
        "postal_code": canonical["extras"]["recipient.postal_code"],
        "country": canonical["extras"]["recipient.country"],
    },
    "items": [
        {**item, "tax_rate": 19} for item in canonical["items"]
    ],
    "tax_entries": [
        {"rate": 19, "basis": canonical["subtotal"], "amount": canonical["tax_amount"]}
    ],
    "tax_total": canonical["tax_amount"],
    "payment": {
        "means": "credit_transfer",
        "iban": "DE89370400440532013000",
        "bic": "COBADEFFXXX",
    },
}


# ── Step 3: Build CII XML via drafthorse (TrustRender wraps it) ──────

print("Step 2: Build CII XML via drafthorse")
xml_bytes = build_invoice_xml(zugferd_data, profile="en16931")
print(f"  → {len(xml_bytes):,} bytes of UN/CEFACT CII XML generated")


# ── Step 4: Generate a visual PDF (your invoice template, simplified) ─

print("Step 3: Render visual PDF (this would be YOUR invoice template)")
pdf = FPDF()
pdf.add_page()
pdf.set_font("Helvetica", "B", 18)
pdf.cell(0, 10, f"Invoice {canonical['invoice_number']}", new_x="LMARGIN", new_y="NEXT")
pdf.ln(2)
pdf.set_font("Helvetica", "", 11)
pdf.cell(0, 6, f"{zugferd_data['seller']['name']}", new_x="LMARGIN", new_y="NEXT")
pdf.cell(0, 6, f"VAT: {zugferd_data['seller']['vat_id']}", new_x="LMARGIN", new_y="NEXT")
pdf.ln(4)
pdf.cell(0, 6, f"Bill to:  {canonical['recipient']['name']}", new_x="LMARGIN", new_y="NEXT")
pdf.cell(0, 6, f"          {canonical['recipient']['address']}", new_x="LMARGIN", new_y="NEXT")
pdf.ln(4)
pdf.cell(0, 6, f"Date: {canonical['invoice_date']}    Due: {canonical['due_date']}", new_x="LMARGIN", new_y="NEXT")
pdf.ln(4)

pdf.set_font("Helvetica", "B", 11)
pdf.cell(95, 6, "Item", border="B")
pdf.cell(20, 6, "Qty", border="B", align="R")
pdf.cell(35, 6, "Unit", border="B", align="R")
pdf.cell(35, 6, "Total", border="B", align="R", new_x="LMARGIN", new_y="NEXT")
pdf.set_font("Helvetica", "", 11)
for item in canonical["items"]:
    pdf.cell(95, 6, item["description"][:55])
    pdf.cell(20, 6, str(int(item["quantity"])), align="R")
    pdf.cell(35, 6, f"EUR {item['unit_price']:,.2f}", align="R")
    pdf.cell(35, 6, f"EUR {item['line_total']:,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

pdf.ln(4)
pdf.cell(150, 6, "Subtotal", align="R")
pdf.cell(35, 6, f"EUR {canonical['subtotal']:,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
pdf.cell(150, 6, f"VAT (19%)", align="R")
pdf.cell(35, 6, f"EUR {canonical['tax_amount']:,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")
pdf.set_font("Helvetica", "B", 11)
pdf.cell(150, 6, "Total", align="R")
pdf.cell(35, 6, f"EUR {canonical['total']:,.2f}", align="R", new_x="LMARGIN", new_y="NEXT")

visual_pdf_bytes = bytes(pdf.output())
print(f"  → {len(visual_pdf_bytes):,} bytes of visual PDF")


# ── Step 5: Embed XML into PDF via factur-x (TrustRender wraps it) ───

print("Step 4: Embed CII XML into PDF as Factur-X / PDF/A-3b")
factur_x_pdf = apply_zugferd(visual_pdf_bytes, xml_bytes, lang="de")
print(f"  → {len(factur_x_pdf):,} bytes of Factur-X compliant PDF")


# ── Step 6: Save and verify ──────────────────────────────────────────

out_path = Path(__file__).parent / "invoice_facturx.pdf"
out_path.write_bytes(factur_x_pdf)
print(f"\nWrote {out_path}")

# Verify XML is XSD-valid using factur-x library
try:
    from facturx import xml_check_xsd
    print("\nStep 5: Verify with factur-x library")
    # xml_check_xsd returns True on success, raises on failure
    is_valid = xml_check_xsd(xml_bytes, flavor="factur-x", level="en16931")
    print(f"  ✓ XML passes EN 16931 XSD validation: {is_valid}")
except ImportError:
    print("\n(install factur-x for XSD verification: pip install factur-x)")
except Exception as exc:
    print(f"  ✗ Verification raised: {exc}")

# Verify the PDF actually contains an embedded file
from pypdf import PdfReader
reader = PdfReader(out_path)
embedded = reader.attachments
print(f"\nEmbedded files in PDF: {list(embedded.keys())}")
assert "factur-x.xml" in embedded, "Factur-X XML not embedded!"
print("✓ factur-x.xml is embedded in the PDF")
