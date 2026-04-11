# E-Invoice Compliance & Claims Audit

Conducted: 2026-04-11
Status: **Resolved** — all findings executed in commit `8b67121`

---

## Executive Verdict

The e-invoicing code is real, wired, and works for the narrow path it covers. But pre-audit, the public-facing language implied more breadth, more validation depth, and more profile coverage than what actually existed.

Three critical issues were found and fixed:

1. **XRechnung contradiction** — website listed it as supported, known-limits said not supported, zero tests existed. Truth test showed Schematron fails with current tooling. **Removed from all public claims.**
2. **"XSD + Schematron validated" implied runtime validation** — actually test-suite only. **Reworded to "Schema-tested CII XML". XSD validation added to preflight().**
3. **"Structured data in, compliant artifact out" was too broad** — sounded like a universal guarantee for one narrow invoice shape. **Replaced with scoped language.**

Additional fix: allowances/charges were silently hardcoded to zero in XML generation. Now rejected at validation time.

---

## Claim-by-Claim Audit

### "Validator-backed e-invoicing"

| Aspect | Assessment |
|--------|-----------|
| What a buyer assumes | Every e-invoice is validated against official schemas before delivery |
| Reality | Field validation at render time. XSD/Schematron in test suite only. |
| Verdict | **Too broad** |
| Action | Changed to "Validated e-invoicing for German B2B" |

### "EN 16931"

| Aspect | Assessment |
|--------|-----------|
| What a buyer assumes | Full EN 16931 compliance across invoice types, tax categories, business rules |
| Reality | EN 16931 profile for one shape: type 380, DE, EUR, single VAT rate, category "S", no allowances |
| Verdict | **NARROW but defensible if scoped** |
| Action | Now always presented with scope qualifier |

### "XSD + Schematron validated"

| Aspect | Assessment |
|--------|-----------|
| What a buyer assumes | Runtime schema validation on every render |
| Reality | Test-suite validation only. Render pipeline does field-level checks. |
| Verdict | **Misleading as positioned** |
| Action | Changed to "Schema-tested CII XML". XSD added to preflight(). |

### "XRechnung"

| Aspect | Assessment |
|--------|-----------|
| What a buyer assumes | XRechnung invoices can be generated for German government procurement |
| Reality | Code paths exist but Schematron fails (guideline ID rejected by factur-x). Zero tests. Internal docs contradicted public claims. |
| Verdict | **Dangerous overclaim** |
| Action | Removed from all public surfaces. Documented as "code path exists, not validated". |

### "Supported invoice shapes" (plural)

| Aspect | Assessment |
|--------|-----------|
| What a buyer assumes | Multiple invoice types supported |
| Reality | One shape: type 380, DE, EUR, single rate, SEPA, no allowances |
| Verdict | **Plural is generous** |
| Action | Replaced XRechnung card with explicit "Scope" card listing constraints |

### "ZUGFeRD / Factur-X"

| Aspect | Assessment |
|--------|-----------|
| What a buyer assumes | Full ZUGFeRD compliance across profiles |
| Reality | EN 16931 profile only |
| Verdict | **Defensible if scoped** |
| Action | No change needed — scope card handles qualification |

### "Embedded XML in PDF/A-3"

| Aspect | Assessment |
|--------|-----------|
| Verdict | **True.** Most defensible claim. Typst renders PDF/A-3b, drafthorse attaches XML, Mustang validated (manual). |
| Action | Added "b" for precision: PDF/A-3b |

### "Structured data in, compliant artifact out"

| Aspect | Assessment |
|--------|-----------|
| What a buyer assumes | Universal compliance pipeline |
| Reality | One JSON schema, one invoice type, DE/EUR/B2B only |
| Verdict | **Most dangerous line** |
| Action | Removed entirely. Replaced with scoped value proposition. |

### "Scoped to DE, EUR, B2B/B2G, single VAT rate"

| Aspect | Assessment |
|--------|-----------|
| Verdict | **Good. Doing honest work.** |
| Action | Made more prominent in all copy |

---

## Top 5 Overclaim Risks (pre-audit)

1. **XRechnung listed as feature, untested, contradicted by internal docs** — Fixed: removed
2. **"XSD + Schematron validated" implied runtime** — Fixed: reworded + XSD in preflight
3. **"Structured data in, compliant artifact out" sounded universal** — Fixed: removed
4. **"Supported invoice shapes" (plural) for one shape** — Fixed: explicit scope card
5. **Allowances/charges silently zeroed** — Fixed: rejected at validation

---

## What Was Done

| Fix | File(s) |
|-----|---------|
| XRechnung removed from public claims | App.jsx, README.md |
| Headline/body copy narrowed | App.jsx |
| XSD validation added to preflight | readiness.py |
| Allowance/charge rejection | zugferd.py |
| XRechnung truth test (Schematron fails) | test_zugferd.py |
| Allowance/charge/discount rejection tests | test_zugferd.py |
| 6 fixture variant tests (XSD-validated) | test_zugferd.py |
| Scope matrix published | einvoice-scope.md |
| Known-limits aligned | known-limits.md |
| Claims matrix updated | claims-matrix.md |

Result: 729 tests, all passing. 14 new compliance-specific tests.

---

## What Is Honestly Claimable Now

- Validated German B2B e-invoicing for a narrow supported shape
- EN 16931 profile (ZUGFeRD / Factur-X)
- Schema-tested CII XML (XSD + Schematron in test suite)
- Preflight XSD validation when facturx available
- Loud failure on unsupported shapes, including allowances/charges
- PDF/A-3b with embedded CII XML

## What Should Not Be Claimed Yet

- XRechnung (Schematron fails with current tooling)
- "Compliant artifact" without scope
- Runtime Schematron validation
- Enterprise-ready e-invoicing
- Broad EN 16931 support
- Production-ready (one fixture, narrow scope)

---

## Next Steps to Strengthen Claims

1. **Mixed VAT rates** — highest buyer impact, closes "demo vs real" gap
2. **Credit notes (type 381)** — no billing system works without cancellations
3. **XRechnung** — integrate KOSIT Schematron, then re-claim with tests
4. **Allowances/charges** — implement instead of just rejecting
5. **Broader fixture corpus** — 5+ validated invoice variants
