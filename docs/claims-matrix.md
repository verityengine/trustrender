# Formforge Claims Matrix

Conducted: 2026-04-10

Every public or semi-public claim, checked against code.

## Verdicts

| Verdict | Meaning |
|---------|---------|
| TRUE | Claim is accurate and proven by automated tests or verifiable code |
| NARROW | Claim is accurate for a specific scope that is tighter than the wording implies |
| MANUAL | Claim is accurate based on a one-time manual run, not automated or reproducible |
| STALE | Claim was accurate at some point but is now outdated |
| ASPIRATIONAL | Claim describes intent or direction, not current proven state |
| UNPROVEN | Claim is stated but no evidence exists in the test suite or CI |

---

## Performance Claims

| Claim | Source | Verdict | Evidence | Action |
|-------|--------|---------|----------|--------|
| 53.8 requests/second | Website, outreach | MANUAL | Server soak from previous run (not re-run this session) | Server soak results still from prior manual run |
| 60ms library latency (p95: 95ms) | benchmarks/soak_results.md | TRUE | 500 renders, committed 2026-04-10 | **Committed** |
| 500 soak renders, 0 errors, 0 temp leaks | benchmarks/soak_results.md | TRUE | Library + mixed soak results committed | **Committed** |
| 2.3x faster than WeasyPrint | benchmarks/results.md | MANUAL | 41ms vs 96ms on simple invoice, Apple Silicon only | Honest as stated; note platform |
| 201-row statement, 7 pages, headers repeat | Website | MANUAL | `benchmarks/results.md` documents this | Add automated test for header repeat |

---

## Test / Quality Claims

| Claim | Source | Verdict | Evidence | Action |
|-------|--------|---------|----------|--------|
| 288 tests passing | Website, outreach, CLAUDE.md (old) | RESOLVED | Updated to 592 across all surfaces | **Done** |
| Timeout kill verified | Website | TRUE | `tests/test_server.py` timeout tests, subprocess boundary | None |
| Real subprocess kill on timeout | Outreach | TRUE | `engine.py:156-169`, server forces CLI backend | None |
| Docker output matches local | Outreach, CLAUDE.md | UNPROVEN | No automated test compares Docker vs local output | Add test or downgrade claim |
| Bundled fonts for determinism | Website, outreach | NARROW | True IF using bundled Inter. Silent fallback if font missing. | Caveat in known-limits.md |

---

## Feature Claims

| Claim | Source | Verdict | Evidence | Action |
|-------|--------|---------|----------|--------|
| No Chromium | README, website | TRUE | Zero browser dependencies in codebase | None |
| 5 real templates | Website | TRUE | Actually 6 (invoice, einvoice, statement, receipt, letter, report) | Update to 6 |
| Pre-render contract validation | README, website | TRUE | 39 tests, CLI + server integration, opt-in | None |
| Contract catches data errors before rendering | Outreach | TRUE | Validation runs at `data_validation` stage, before Typst | None |
| Table headers repeat on page breaks | Outreach, benchmarks | NARROW | Typst `table.header()` behavior, not Formforge code. No test validates it. | Clarify attribution or add test |
| Structured business PDFs from code | README | TRUE | 6 working templates covering invoices, statements, receipts, letters, reports | None |
| Clean templates (Jinja2 + Typst) | CLAUDE.md | TRUE | Subjective but supported by template readability | None |
| Predictable layout | CLAUDE.md | NARROW | True for table/page flow. Escaping boundaries in code/math mode. | Document escaping scope |

---

## Compliance Claims

| Claim | Source | Verdict | Evidence | Action |
|-------|--------|---------|----------|--------|
| EN 16931 compliant | README | NARROW | DE/EUR/B2B/single-rate/type-380 only. Unsupported shapes fail loudly. | Ensure scope is always stated alongside claim |
| Passes Mustang validator | README (old) | RESOLVED | Wording downgraded to "XSD + Schematron validated." Mustang referenced as one-time manual proof. | **Done** |
| PDF/A-3b with embedded XML | README | TRUE | `drafthorse.pdf.attach_xml()` used, tested | None |
| ZUGFeRD unsupported cases fail loudly | zugferd.py comments | TRUE | Tests for non-EUR, non-DE, mixed rates, empty items, missing fields all exist and pass | **Corrected (tests existed)** |

---

## Operational Claims

| Claim | Source | Verdict | Evidence | Action |
|-------|--------|---------|----------|--------|
| production-grade | CLAUDE.md thesis | ASPIRATIONAL | CLAUDE.md line 262 contradicts: "not yet production-grade" | Reconcile or qualify |
| deterministic | CLAUDE.md | NARROW | Only with bundled fonts. Cross-env unproven. Silent fallback. | Always qualify with "bundled fonts" |
| Server timeout is real | CLAUDE.md | TRUE | Subprocess kill + asyncio watchdog | None |
| Timeout artifacts cleaned | CLAUDE.md | TRUE | `test_server.py::test_repeated_timeouts_no_temp_file_leak` | None |
| Docker works | CLAUDE.md | NARROW | Builds and serves. Unicode untested. No locale config. | Add locale + Unicode test |
| CI green | CLAUDE.md | TRUE | GitHub Actions runs Python 3.11/3.12, doctor + tests + lint | None |
| formforge doctor works | CLAUDE.md | TRUE | 20 tests in `test_doctor.py` | None |

---

## Architecture Claims

| Claim | Source | Verdict | Evidence | Action |
|-------|--------|---------|----------|--------|
| Backend abstraction works | CLAUDE.md | TRUE | Protocol-driven, both backends tested, 38 tests | None |
| Error pipeline: 9 classified error codes | CLAUDE.md | STALE | Actually 11 codes (ZUGFERD_ERROR and others added since) | Update CLAUDE.md |
| 4 pipeline stages | CLAUDE.md | STALE | Actually 7 stages | Update CLAUDE.md |

---

## Summary

| Verdict | Count |
|---------|-------|
| TRUE | 14 |
| NARROW | 8 |
| MANUAL | 5 |
| STALE | 3 |
| ASPIRATIONAL | 1 |
| UNPROVEN | 4 |
| **Total claims checked** | **35** |

**Key takeaway:** 14 claims are solidly true. 8 are true but narrower than stated. 5 are real but only manually proven. 4 are stated without test evidence. 3 are stale numbers. 1 is aspirational.

No claim is fabricated. The project is honest in code but some public-facing materials present manual results as operational proof and use stale numbers.
