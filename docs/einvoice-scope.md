# E-Invoice Scope Matrix

Updated: 2026-04-11

Single authoritative reference for what Formforge supports, rejects, and does not claim for e-invoicing.

---

## Supported (renders valid PDF/A-3b with embedded CII XML)

| Dimension | Supported value |
|-----------|----------------|
| Profile | EN 16931 (ZUGFeRD / Factur-X) |
| Invoice type | Standard VAT invoice (type code 380) |
| Country | Germany (DE) — seller and delivery |
| Currency | EUR |
| Tax category | Standard rate ("S") |
| Tax rates | Single rate per invoice (e.g., 19%) |
| Payment means | SEPA credit transfer (code 58), SEPA direct debit (code 59) |
| Line items | Description, quantity, unit, unit_price, tax_rate, line_total |
| Totals | subtotal, tax_total, total (pre-computed, numeric) |
| PDF standard | PDF/A-3b with embedded CII XML |
| Delivery | Delivery date = invoice date; delivery country from buyer or seller |

## Rejected loudly (validation error before render)

| Scenario | Error behavior |
|----------|---------------|
| Non-EUR currency (e.g., USD, GBP) | `ContractError` on `currency` field |
| Non-DE country | `ContractError` on `seller.country` |
| Mixed tax rates within one invoice | `ContractError` on `items` — lists found rates |
| Missing required fields (invoice_number, seller.vat_id, buyer.name, etc.) | `ContractError` per missing field |
| Missing payment details | `ContractError` on `payment` |
| Non-numeric totals | `ContractError` on `subtotal`, `tax_total`, or `total` |
| Unsupported payment means | `ContractError` on `payment.means` |
| Missing IBAN for credit transfer | `ContractError` on `payment.iban` |
| Allowances, charges, or discounts present in data | `ContractError` — not supported in v1 |
| Empty line items list | `ContractError` on `items` |

## Not claimed (no code path, no validation, no test)

| Scenario | Status | Notes |
|----------|--------|-------|
| Credit notes (type 381) | Not implemented | No type code support beyond 380 |
| Reverse charge (VAT category "AE") | Not implemented | Only "S" (standard) category |
| Intra-community supply | Not implemented | DE domestic only |
| Cross-border invoicing | Not implemented | DE only |
| Invoicing periods (BT-73/BT-74) | Not implemented | Uses delivery date only |
| Buyer purchase order reference (BT-13) | Not implemented | |
| Partial shipments / multiple deliveries | Not implemented | |
| Non-SEPA payment means | Not implemented | Codes 58/59 only |
| Extended profile | Not implemented | EN 16931 only |
| Basic profile | Not implemented | EN 16931 only |
| Minimum profile | Not implemented | EN 16931 only |

## XRechnung status

Code paths exist for XRechnung (guideline ID, Leitweg-ID/BT-10, BR-DE-5 seller contact, electronic addresses). However:

- Generated XML passes XSD validation
- Generated XML **fails** Schematron validation (guideline ID not in factur-x allowed set)
- Proper validation requires KOSIT XRechnung Schematron rules (not currently integrated)
- Zero tests exist for XRechnung-specific paths

**XRechnung is not a supported profile.** The code path exists for future work but should not be used in production.

## Validation layers

| Layer | When it runs | What it checks |
|-------|-------------|----------------|
| Field validation (`validate_zugferd_invoice_data`) | `render()`, `preflight()` | Required fields, currency, country, tax rate, payment, allowances/charges |
| XSD schema validation (`facturx.xml_check_xsd`) | `preflight()` (if facturx installed) | CII XML structure against EN 16931 XSD |
| Schematron validation (`facturx.xml_check_schematron`) | Test suite only | EN 16931 business rules |
| Mustang reference validator | Manual, one-time (see zugferd-prototype.md) | Full PDF/A-3b + XML compliance |

## Proof status

| What | Proof level |
|------|-------------|
| EN 16931 simple invoice (DE/EUR/19%/type 380) | Schema-tested (XSD + Schematron pass in test suite), Mustang-validated (one-time manual) |
| PDF/A-3b with embedded XML | Tested (round-trip extraction verified), Mustang-validated (one-time manual) |
| Field validation rejects unsupported shapes | Tested (10 validation tests) |
| Allowance/charge rejection | Tested |
| XRechnung | Schematron fails — not proven |
| Credit notes, reverse charge, mixed VAT | No code, no tests |
