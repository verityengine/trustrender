"""Ugly-data stress tests across the full template corpus.

Tests realistic messy data that could break rendering:
- Absurdly long company names
- Long addresses
- Unicode characters
- Empty optional fields
- Huge currency values
- Weird punctuation
- Multiline notes
- Special characters in every field
"""

from pathlib import Path

from typeset import render

EXAMPLES = Path("examples")


def assert_valid_pdf(pdf_bytes: bytes):
    assert pdf_bytes[:5] == b"%PDF-", "Not a valid PDF"
    assert len(pdf_bytes) > 1000, "PDF suspiciously small"


# --- Invoice ugly data ---

class TestInvoiceUglyData:
    TEMPLATE = EXAMPLES / "invoice.j2.typ"

    def _base_data(self, **overrides):
        data = {
            "invoice_number": "INV-001",
            "invoice_date": "Jan 1, 2026",
            "due_date": "Feb 1, 2026",
            "payment_terms": "Net 30",
            "sender": {
                "name": "Sender Co",
                "address_line1": "123 Main St",
                "address_line2": "City, ST 00000",
                "email": "a@b.com",
            },
            "recipient": {
                "name": "Recipient Co",
                "address_line1": "456 Oak Ave",
                "address_line2": "Town, ST 11111",
                "email": "x@y.com",
            },
            "items": [
                {
                    "num": 1,
                    "description": "Service",
                    "qty": 1,
                    "unit_price": "$100.00",
                    "amount": "$100.00",
                }
            ],
            "subtotal": "$100.00",
            "tax_rate": "0%",
            "tax_amount": "$0.00",
            "total": "$100.00",
            "notes": "Thanks.",
        }
        data.update(overrides)
        return data

    def test_absurdly_long_company_name(self):
        data = self._base_data()
        data["sender"]["name"] = (
            "The Extremely Long International Conglomerate of Business "
            "Operations and Strategic Consulting Services Inc."
        )
        assert_valid_pdf(render(self.TEMPLATE, data))

    def test_long_address(self):
        data = self._base_data()
        data["recipient"]["address_line1"] = (
            "12345 North Southeast Boulevard, Building C, "
            "Suite 4200, Wing B, Floor 37"
        )
        assert_valid_pdf(render(self.TEMPLATE, data))

    def test_unicode_company_and_items(self):
        data = self._base_data()
        data["sender"]["name"] = "Schneider & Muller GmbH"
        data["items"] = [
            {
                "num": 1,
                "description": "Geschaftsberatung und Strategieentwicklung",
                "qty": 1,
                "unit_price": "$5.000,00",
                "amount": "$5.000,00",
            }
        ]
        assert_valid_pdf(render(self.TEMPLATE, data))

    def test_huge_currency_values(self):
        data = self._base_data()
        data["subtotal"] = "$1,234,567,890.99"
        data["tax_amount"] = "$104,938,270.73"
        data["total"] = "$1,339,506,161.72"
        assert_valid_pdf(render(self.TEMPLATE, data))

    def test_weird_punctuation_in_description(self):
        data = self._base_data()
        data["items"] = [
            {
                "num": 1,
                "description": 'Widget "Pro" (v2.0) -- 50% off! $$$',
                "qty": 1,
                "unit_price": "$49.99",
                "amount": "$49.99",
            }
        ]
        assert_valid_pdf(render(self.TEMPLATE, data))

    def test_multiline_notes(self):
        data = self._base_data()
        data["notes"] = (
            "Line 1 of notes. "
            "Line 2 with special chars: $100 #ref @mention. "
            "Line 3 with unicode. "
            "Line 4: please pay promptly."
        )
        assert_valid_pdf(render(self.TEMPLATE, data))

    def test_empty_optional_fields(self):
        data = self._base_data()
        data["notes"] = ""
        data["sender"]["email"] = ""
        data["recipient"]["email"] = ""
        assert_valid_pdf(render(self.TEMPLATE, data))

    def test_many_items(self):
        data = self._base_data()
        data["items"] = [
            {
                "num": i,
                "description": f"Item {i}: {'A' * 60}",
                "qty": i,
                "unit_price": f"${i * 100:,.2f}",
                "amount": f"${i * i * 100:,.2f}",
            }
            for i in range(1, 51)
        ]
        assert_valid_pdf(render(self.TEMPLATE, data))


# --- Statement ugly data ---

class TestStatementUglyData:
    TEMPLATE = EXAMPLES / "statement.j2.typ"

    def _base_data(self, **overrides):
        data = {
            "company": {
                "name": "Co",
                "address_line1": "Addr",
                "address_line2": "City",
                "email": "a@b.com",
                "phone": "555-0000",
            },
            "customer": {
                "name": "Cust",
                "account_number": "ACCT-001",
                "address_line1": "Addr",
                "address_line2": "City",
                "email": "x@y.com",
            },
            "statement_date": "Jan 1, 2026",
            "period": "Dec 2025",
            "opening_balance": "$0.00",
            "closing_balance": "$100.00",
            "total_charges": "$100.00",
            "total_payments": "$0.00",
            "transactions": [
                {
                    "date": "Dec 01",
                    "description": "Opening Balance",
                    "reference": "",
                    "amount": "",
                    "balance": "$0.00",
                },
                {
                    "date": "Dec 15",
                    "description": "Charge",
                    "reference": "INV-001",
                    "amount": "$100.00",
                    "balance": "$100.00",
                },
            ],
            "aging": {
                "current": "$100.00",
                "days_30": "$0.00",
                "days_60": "$0.00",
                "days_90": "$0.00",
                "total": "$100.00",
            },
            "notes": "Pay soon.",
        }
        data.update(overrides)
        return data

    def test_long_transaction_descriptions(self):
        data = self._base_data()
        data["transactions"] = [
            {
                "date": "Dec 01",
                "description": (
                    "Emergency after-hours database migration and failover "
                    "configuration including weekend support and post-migration "
                    "performance validation testing across all production environments"
                ),
                "reference": "INV-2026-LONGREF-001",
                "amount": "$15,000.00",
                "balance": "$15,000.00",
            }
        ]
        assert_valid_pdf(render(self.TEMPLATE, data))

    def test_negative_values(self):
        data = self._base_data()
        data["transactions"] = [
            {
                "date": "Dec 01",
                "description": "Credit",
                "reference": "CR-001",
                "amount": "-$5,000.00",
                "balance": "-$5,000.00",
            }
        ]
        data["closing_balance"] = "-$5,000.00"
        assert_valid_pdf(render(self.TEMPLATE, data))

    def test_many_transactions(self):
        data = self._base_data()
        data["transactions"] = [
            {
                "date": f"Dec {i:02d}",
                "description": f"Transaction #{i}",
                "reference": f"REF-{i:04d}",
                "amount": f"${i * 50:,.2f}",
                "balance": f"${i * 50:,.2f}",
            }
            for i in range(1, 61)
        ]
        assert_valid_pdf(render(self.TEMPLATE, data))


# --- Receipt ugly data ---

class TestReceiptUglyData:
    TEMPLATE = EXAMPLES / "receipt.j2.typ"

    def _base_data(self, **overrides):
        data = {
            "company": {
                "name": "Shop",
                "address_line1": "123 St",
                "address_line2": "City, ST",
                "phone": "555-0000",
                "website": "shop.com",
            },
            "receipt_number": "REC-001",
            "date": "Jan 1, 2026",
            "time": "12:00 PM",
            "cashier": "Staff",
            "register": "POS-01",
            "items": [
                {
                    "description": "Item",
                    "qty": 1,
                    "unit_price": "$10.00",
                    "amount": "$10.00",
                }
            ],
            "subtotal": "$10.00",
            "tax_label": "Tax (8%)",
            "tax_amount": "$0.80",
            "total": "$10.80",
            "payment": {"method": "Cash", "last_four": "", "auth_code": ""},
            "amount_tendered": "$11.00",
            "change_due": "$0.20",
            "footer_message": "Thanks!",
        }
        data.update(overrides)
        return data

    def test_long_item_names(self):
        data = self._base_data()
        data["items"] = [
            {
                "description": (
                    "Organic Free-Range Triple-Filtered Cold Brew Coffee "
                    "with Oat Milk and Madagascar Vanilla Extract (Venti)"
                ),
                "qty": 1,
                "unit_price": "$8.95",
                "amount": "$8.95",
            }
        ]
        assert_valid_pdf(render(self.TEMPLATE, data))

    def test_long_company_name(self):
        data = self._base_data()
        data["company"]["name"] = (
            "The Artisanal Handcrafted Organic Farm-to-Table Cafe & Bakery"
        )
        assert_valid_pdf(render(self.TEMPLATE, data))

    def test_many_items(self):
        data = self._base_data()
        data["items"] = [
            {
                "description": f"Menu Item #{i}",
                "qty": i,
                "unit_price": f"${i + 0.99:.2f}",
                "amount": f"${i * (i + 0.99):.2f}",
            }
            for i in range(1, 21)
        ]
        assert_valid_pdf(render(self.TEMPLATE, data))


# --- Letter ugly data ---

class TestLetterUglyData:
    TEMPLATE = EXAMPLES / "letter.j2.typ"

    def _base_data(self, **overrides):
        data = {
            "sender": {
                "name": "Sender Co",
                "title": "Dept",
                "address_line1": "123 St",
                "address_line2": "City, ST",
                "phone": "555-0000",
                "email": "a@b.com",
            },
            "recipient": {
                "name": "Jane Doe",
                "title": "CEO",
                "company": "Other Co",
                "address_line1": "456 Ave",
                "address_line2": "Town, ST",
            },
            "date": "Jan 1, 2026",
            "subject": "Test Subject",
            "salutation": "Dear Jane,",
            "body_paragraphs": ["Paragraph one.", "Paragraph two."],
            "closing": "Regards,",
            "signature_name": "John Smith",
            "signature_title": "Manager",
            "signature_company": "Sender Co",
            "enclosures": [],
            "cc": [],
        }
        data.update(overrides)
        return data

    def test_long_subject_line(self):
        data = self._base_data()
        data["subject"] = (
            "Regarding the Proposed Amendment to Section 14.3(b) of the Master "
            "Services Agreement Dated November 15, 2025, as Modified by "
            "Addendum C Executed March 1, 2026"
        )
        assert_valid_pdf(render(self.TEMPLATE, data))

    def test_many_paragraphs(self):
        data = self._base_data()
        data["body_paragraphs"] = [
            f"Paragraph {i}: {'Lorem ipsum dolor sit amet. ' * 5}"
            for i in range(1, 11)
        ]
        assert_valid_pdf(render(self.TEMPLATE, data))

    def test_unicode_names(self):
        data = self._base_data()
        data["recipient"]["name"] = "Francois-Xavier Leblanc"
        data["sender"]["name"] = "Muller & Schmidt GmbH"
        assert_valid_pdf(render(self.TEMPLATE, data))

    def test_empty_enclosures_and_cc(self):
        data = self._base_data()
        data["enclosures"] = []
        data["cc"] = []
        assert_valid_pdf(render(self.TEMPLATE, data))

    def test_many_enclosures(self):
        data = self._base_data()
        data["enclosures"] = [f"Document {i}: {'Title ' * 5}" for i in range(1, 8)]
        data["cc"] = [f"Person {i}, Department {i}" for i in range(1, 6)]
        assert_valid_pdf(render(self.TEMPLATE, data))


# --- Report ugly data ---

class TestReportUglyData:
    TEMPLATE = EXAMPLES / "report.j2.typ"

    def _base_data(self, **overrides):
        data = {
            "company": {"name": "Co", "department": "Dept"},
            "title": "Report",
            "subtitle": "Sub",
            "date": "Jan 1, 2026",
            "prepared_by": "Author",
            "period": "Q1 2026",
            "executive_summary": "Summary text.",
            "metrics": [
                {
                    "label": "Metric",
                    "value": "100",
                    "target": ">50",
                    "status": "above",
                }
            ],
            "incidents": [],
            "spend_by_service": [
                {
                    "service": "Service A",
                    "q1_spend": "$1,000",
                    "q4_spend": "$1,100",
                    "change": "-9.1%",
                }
            ],
            "recommendations": ["Do thing 1."],
        }
        data.update(overrides)
        return data

    def test_long_executive_summary(self):
        data = self._base_data()
        data["executive_summary"] = "Important finding. " * 100
        assert_valid_pdf(render(self.TEMPLATE, data))

    def test_less_than_in_targets(self):
        data = self._base_data()
        data["metrics"] = [
            {"label": "Errors", "value": "2", "target": "<5", "status": "met"},
            {"label": "Latency", "value": "15ms", "target": "<50ms", "status": "above"},
        ]
        assert_valid_pdf(render(self.TEMPLATE, data))

    def test_many_incidents(self):
        data = self._base_data()
        data["incidents"] = [
            {
                "id": f"INC-{i:04d}",
                "date": f"Jan {i}",
                "severity": "P1" if i % 3 == 0 else "P2",
                "duration": f"{i * 5} min",
                "description": f"Incident {i}: {'Details. ' * 10}",
                "root_cause": f"Root cause {i}.",
                "resolution": f"Resolution {i}.",
            }
            for i in range(1, 8)
        ]
        assert_valid_pdf(render(self.TEMPLATE, data))

    def test_currency_with_special_chars(self):
        data = self._base_data()
        data["spend_by_service"] = [
            {
                "service": "Database (RDS/DynamoDB) + $extras",
                "q1_spend": "$99,999.99",
                "q4_spend": "$88,888.88",
                "change": "+12.5%",
            }
        ]
        assert_valid_pdf(render(self.TEMPLATE, data))
