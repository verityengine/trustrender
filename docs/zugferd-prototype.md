# ZUGFeRD EN 16931 Prototype — Proof Checklist

## Date: 2026-04-10

## Scope

- Profile: EN 16931 only
- Country: Germany (DE)
- Currency: EUR
- Tax: standard VAT 19%, single rate
- Invoice type: domestic B2B standard VAT invoice (type code 380)
- Validator: factur-x XSD + Schematron (official Factur-X 1.08 rules)

## Explicitly unsupported

- Credit notes
- Reverse charge
- Intra-community
- Mixed tax rates
- Cross-border
- Non-EUR currencies
- Non-DE countries

## Fixture

- Data: `examples/einvoice_data.json`
- Template: `examples/invoice.j2.typ` (existing invoice used for visual rendering)
- 3 line items, 19% VAT, EUR, DE seller + DE buyer

## Results

| Step | Check | Result |
|------|-------|--------|
| 1 | Invoice data validation (`validate_zugferd_invoice_data`) | PASS |
| 2 | CII XML generation (`build_invoice_xml`) | PASS (8,472 bytes) |
| 3 | XSD validation (`facturx.xml_check_xsd`) | PASS |
| 4 | Schematron validation (`facturx.xml_check_schematron`) | PASS |
| 5 | Visual PDF render (Typst via formforge) | PASS (56,639 bytes) |
| 6 | ZUGFeRD PDF/A-3b combination (`apply_zugferd`) | PASS (43,049 bytes) |
| 7 | XML extracted from output PDF (`get_xml_from_pdf`) | PASS (filename=factur-x.xml, 8,472 bytes) |
| 8 | Extracted XML re-validated (XSD + Schematron) | PASS |
| 9 | Round-trip integrity (input XML == extracted XML) | PASS |

## Schematron issues encountered and fixed

1. **Guideline ID:** Initial value `urn:cen.eu:en16931:2017#conformant#urn:zugferd.de:2p1:en16931` rejected. Correct value: `urn:cen.eu:en16931:2017`
2. **Empty delivery element:** `ApplicableHeaderTradeDelivery` was empty. Fixed by adding delivery date (BT-72) and country (BT-80).
3. **Missing delivery date:** BR-FX-EN-04 requires actual delivery date, invoicing period, or line-level period. Fixed by setting delivery event occurrence to invoice date.

## Dependencies

- `drafthorse>=2024.0` — XML generation + PDF attachment (single dependency handles both)
- `factur-x>=4.0` — used only for XSD/Schematron validation (not required at runtime for PDF generation)

## Architecture

```
einvoice_data.json (raw numeric amounts, VAT IDs, IBAN)
    → validate_zugferd_invoice_data() — EN 16931 field validation
    → build_invoice_xml() — data → drafthorse Document → CII XML bytes
    → formforge.render() — template + data → Typst → visual PDF bytes
    → apply_zugferd() — drafthorse.pdf.attach_xml(pdf, xml) → PDF/A-3b
    → output: ZUGFeRD-compliant PDF with embedded XML
```

## Files

- `src/formforge/zugferd.py` — validation, XML generation, PDF post-processing
- `examples/einvoice_data.json` — EN 16931 data fixture

## Verdict

Step 1 proof complete. The compliance path works. XML passes both XSD and Schematron validation. PDF/A-3b output contains correctly embedded XML that round-trips exactly.

Ready for Step 2: wire into `render()`, CLI, server.

## Mustang CLI validation

### Command

```bash
docker build -t mustang-validator build/mustang
docker run --rm --platform linux/amd64 -v /tmp:/data mustang-validator \
  --action validate --source /data/zugferd_en16931.pdf
```

### Exit code: 0 (VALID)

### Results (with Typst `pdf_standards=['a-3b']`)

| Component | Status | Notes |
|-----------|--------|-------|
| PDF/A-3b | **valid** | `isCompliant=true, assertions=[]` — zero violations |
| XML | **valid** | EN 16931 profile detected. 26 rules fired, 8 notices (all type 27 = informational, XRechnung-specific, non-blocking for EN 16931) |
| Overall | **valid** | Exit code 0. Both PDF and XML pass. |

### Previous run (without `pdf_standards=['a-3b']`)

PDF/A-3b was `invalid` due to Typst rendering transparency without blending colour space. Fixed by passing `pdf_standards=['a-3b']` to `typst.compile()`. This is a one-line change in the Step 2 pipeline wiring.

### XRechnung notices (informational, non-blocking for EN 16931)

These are from XRechnung-specific rules (German CIUS), not EN 16931 core. Our invoice targets EN 16931, not XRechnung:

1. `PEPPOL-EN16931-R001` — Business process not provided (XRechnung requirement)
2. `PEPPOL-EN16931-R020` — Seller electronic address not provided
3. `PEPPOL-EN16931-R010` — Buyer electronic address not provided
4. `BR-DE-15` — Buyer reference (BT-10) not provided
5. `BR-DE-21` — Specification identifier doesn't match XRechnung format
6. `BR-DE-5` — Seller contact point (PersonName/DepartmentName) not provided
7. `BR-DE-10` — Deliver-to city not provided (when delivery address is present)
8. `BR-DE-11` — Deliver-to post code not provided (when delivery address is present)

### PDF/A-3b fix

Resolved. Typst renders compliant PDF/A-3b when given `pdf_standards=['a-3b']`. Then `drafthorse.pdf.attach_xml()` adds ZUGFeRD metadata. Both Mustang checks pass.
