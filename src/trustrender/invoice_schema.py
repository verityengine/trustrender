"""Canonical invoice schema for structured ingestion.

Defines the target shape that messy invoice data compiles into.
One schema, one template target (invoice.j2.typ), one document class.

Every field carries provenance so callers know where each value came from.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

# ---------------------------------------------------------------------------
# Provenance tracking
# ---------------------------------------------------------------------------


@dataclass
class FieldProvenance:
    """Tracks where a canonical field value came from."""

    canonical_name: str
    source: Literal["exact", "alias", "computed", "default", "missing"]
    original_key: str | None = None  # the messy key name, if alias
    original_value: str | None = None  # before coercion, as string
    message: str | None = None  # human-readable explanation

    def to_dict(self) -> dict:
        d: dict = {"canonical_name": self.canonical_name, "source": self.source}
        if self.original_key is not None:
            d["original_key"] = self.original_key
        if self.original_value is not None:
            d["original_value"] = self.original_value
        if self.message is not None:
            d["message"] = self.message
        return d


# ---------------------------------------------------------------------------
# Canonical schema dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Address:
    name: str = ""
    address: str = ""
    email: str = ""

    def to_dict(self) -> dict:
        return {"name": self.name, "address": self.address, "email": self.email}


@dataclass
class LineItem:
    description: str = ""
    quantity: float = 0.0
    unit_price: float = 0.0
    line_total: float = 0.0
    num: int = 0

    def to_dict(self) -> dict:
        return {
            "num": self.num,
            "description": self.description,
            "quantity": self.quantity,
            "unit_price": self.unit_price,
            "line_total": self.line_total,
        }


@dataclass
class CanonicalInvoice:
    # Identity (required)
    invoice_number: str = ""
    invoice_date: str = ""  # YYYY-MM-DD
    due_date: str = ""  # YYYY-MM-DD
    sender: Address = field(default_factory=Address)
    recipient: Address = field(default_factory=Address)
    items: list[LineItem] = field(default_factory=list)

    # Totals (computed if missing)
    subtotal: float = 0.0
    tax_rate: float = 0.0
    tax_amount: float = 0.0
    total: float = 0.0

    # Optional
    currency: str = "USD"
    payment_terms: str = ""
    notes: str = ""

    # Unknown fields preserved
    extras: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "invoice_number": self.invoice_number,
            "invoice_date": self.invoice_date,
            "due_date": self.due_date,
            "sender": self.sender.to_dict(),
            "recipient": self.recipient.to_dict(),
            "items": [item.to_dict() for item in self.items],
            "subtotal": self.subtotal,
            "tax_rate": self.tax_rate,
            "tax_amount": self.tax_amount,
            "total": self.total,
            "currency": self.currency,
            "payment_terms": self.payment_terms,
            "notes": self.notes,
            "extras": self.extras,
        }

    def to_template_shape(self) -> dict:
        """Reshape canonical payload to invoice.j2.typ expected shape.

        Target matches builtin_templates/invoice_data.json:
        - Amounts as display strings: "$4,500.00"
        - Dates as display strings: "April 10, 2026"
        - Items keyed as num/description/qty/unit_price/amount
        """
        return {
            "invoice_number": self.invoice_number,
            "invoice_date": _format_display_date(self.invoice_date),
            "due_date": _format_display_date(self.due_date),
            "payment_terms": self.payment_terms,
            "sender": self.sender.to_dict(),
            "recipient": self.recipient.to_dict(),
            "items": [
                {
                    "num": item.num,
                    "description": item.description,
                    "qty": item.quantity,
                    "unit_price": _format_currency(item.unit_price, self.currency),
                    "amount": _format_currency(item.line_total, self.currency),
                }
                for item in self.items
            ],
            "subtotal": _format_currency(self.subtotal, self.currency),
            "tax_rate": f"{self.tax_rate}%" if self.tax_rate else "0%",
            "tax_amount": _format_currency(self.tax_amount, self.currency),
            "total": _format_currency(self.total, self.currency),
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Display formatting helpers
# ---------------------------------------------------------------------------

_CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£", "JPY": "¥", "CHF": "CHF "}


def _format_currency(value: float, currency: str = "USD") -> str:
    """Format a numeric amount as a display currency string."""
    symbol = _CURRENCY_SYMBOLS.get(currency.upper(), currency + " ")
    if value < 0:
        return f"-{symbol}{abs(value):,.2f}"
    return f"{symbol}{value:,.2f}"


def _format_display_date(iso_date: str) -> str:
    """Convert YYYY-MM-DD to display format like 'April 10, 2026'."""
    if not iso_date:
        return ""
    try:
        dt = datetime.strptime(iso_date, "%Y-%m-%d")
        return dt.strftime("%B %d, %Y").replace(" 0", " ")
    except ValueError:
        return iso_date
