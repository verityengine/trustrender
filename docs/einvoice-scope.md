# E-Invoice Scope Matrix

Updated: 2026-04-12

Single authoritative reference for what TrustRender supports, rejects, and does not claim for e-invoicing.

---

## Supported (renders valid PDF/A-3b with embedded CII XML)

| Dimension | Supported value |
|-----------|----------------|
| Profile | EN 16931 (ZUGFeRD / Factur-X) |
| Invoice type | Standard invoice (380) and credit note (381) |
| Country | Germany (DE) — seller and delivery |
| Currency | EUR |
| Tax category | Standard rate ("S") |
| Tax rates | Single or mixed rates per invoice (e.g., 7% + 19%) |
| Payment means | SEPA credit transfer (code 58), SEPA direct debit (code 59) |
| Line items | Description, quantity, unit, unit_price, tax_rate, line_total |
| Totals | subtotal, tax_total, total (pre-computed, numeric, positive) |
| Credit note reference | referenced_invoice (required for type 381, BT-25) |
| PDF standard | PDF/A-3b with embedded CII XML |
| Delivery | Delivery date = invoice date; delivery country from buyer or seller |

## Rejected loudly (validation error before render)

| Scenario | Error behavior |
|----------|---------------|
| Non-EUR currency (e.g., USD, GBP) | `ContractError` on `currency` field |
| Non-DE country | `ContractError` on `seller.country` |
| Missing tax_entries for an item rate | `ContractError` on `tax_entries` — bidirectional consistency check |
| Orphan tax_entries rate with non-zero basis | `ContractError` on `tax_entries` — rate not used by any item |
| Missing required fields (invoice_number, seller.vat_id, buyer.name, etc.) | `ContractError` per missing field |
| Missing payment details | `ContractError` on `payment` |
| Non-numeric totals | `ContractError` on `subtotal`, `tax_total`, or `total` |
| Unsupported payment means | `ContractError` on `payment.means` |
| Missing IBAN for credit transfer | `ContractError` on `payment.iban` |
| Allowances, charges, or discounts present in data | `ContractError` — not supported in v1 |
| Empty line items list | `ContractError` on `items` |
| Unsupported invoice type (not 380 or 381) | `ContractError` on `invoice_type` |
| `referenced_invoice` on type 380 | `ContractError` — only valid for credit notes |
| Type 381 without `referenced_invoice` | `ContractError` — required for credit notes |

## Not claimed (no code path, no validation, no test)

| Scenario | Status | Notes |
|----------|--------|-------|
| ~~Credit notes (type 381)~~ | **Supported** | Type 381 with referenced_invoice (BT-25) |
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
| EN 16931 standard invoice (DE/EUR/type 380) | Schema-tested (XSD + Schematron pass in test suite), Mustang-validated (one-time manual) |
| EN 16931 credit note (DE/EUR/type 381) | Schema-tested (XSD + Schematron pass in test suite) |
| PDF/A-3b with embedded XML | Tested (round-trip extraction verified), Mustang-validated (one-time manual) |
| Field validation rejects unsupported shapes | Tested (10 validation tests) |
| Allowance/charge rejection | Tested |
| Mixed VAT rates (7% + 19%) | Schema-tested (XSD + Schematron pass), render integration tested |
| Reverse charge | No code, no tests |
