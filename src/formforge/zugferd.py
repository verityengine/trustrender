"""ZUGFeRD EN 16931 e-invoice generation.

Converts Formforge invoice data to CII XML, renders the visual PDF via Typst,
and combines them into a ZUGFeRD-compliant PDF/A-3b document.

Supported scope (v1):
    - Profile: EN 16931 only
    - Country: Germany (DE)
    - Currency: EUR only
    - Tax: standard VAT (19%) — single rate per invoice
    - Invoice type: domestic B2B standard VAT invoice (type code 380)

Explicitly unsupported:
    - Credit notes, reverse charge, intra-community, mixed tax rates,
      cross-border, non-EUR currencies, non-DE countries

Uses ``drafthorse`` for both XML generation and PDF attachment.
No ``factur-x`` dependency needed — drafthorse handles the full pipeline.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from pathlib import Path

from drafthorse.models.accounting import ApplicableTradeTax
from drafthorse.models.document import Document
from drafthorse.models.party import TaxRegistration
from drafthorse.models.payment import PaymentMeans, PaymentTerms
from drafthorse.models.tradelines import LineItem
from drafthorse.pdf import attach_xml

from .contract import ContractError


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PAYMENT_MEANS_CODES = {
    "credit_transfer": "58",  # SEPA credit transfer
    "direct_debit": "59",     # SEPA direct debit
}

_SUPPORTED_CURRENCIES = {"EUR"}
_SUPPORTED_COUNTRIES = {"DE"}


# ---------------------------------------------------------------------------
# Invoice data validation (EN 16931 specific)
# ---------------------------------------------------------------------------

def validate_zugferd_invoice_data(
    data: dict, *, profile: str = "en16931",
) -> list[ContractError]:
    """Validate that data satisfies EN 16931 / XRechnung requirements.

    This is stricter than generic template contract validation.  It checks
    fields needed for CII XML generation, not just template rendering.

    Fails loudly on unsupported invoice shapes.
    """
    errors: list[ContractError] = []

    # --- Required top-level fields ---
    for field in ("invoice_number", "invoice_date", "due_date", "currency"):
        if field not in data or not data[field]:
            errors.append(ContractError(
                path=field,
                message=f"required for EN 16931",
                expected="string",
                actual="missing",
            ))

    # --- Unsupported shapes: fail loudly ---
    currency = data.get("currency", "")
    if currency and currency not in _SUPPORTED_CURRENCIES:
        errors.append(ContractError(
            path="currency",
            message=f"only EUR is supported in v1, got '{currency}'",
            expected="EUR",
            actual=currency,
        ))

    # --- Seller ---
    seller = data.get("seller")
    if not isinstance(seller, dict):
        errors.append(ContractError(
            path="seller", message="required object", expected="object", actual="missing",
        ))
    else:
        for field in ("name", "address", "city", "postal_code", "country"):
            if not seller.get(field):
                errors.append(ContractError(
                    path=f"seller.{field}",
                    message=f"required for EN 16931",
                    expected="string",
                    actual="missing",
                ))
        if not seller.get("vat_id"):
            errors.append(ContractError(
                path="seller.vat_id",
                message="seller VAT ID required for EN 16931",
                expected="string (e.g. DE123456789)",
                actual="missing",
            ))
        country = seller.get("country", "")
        if country and country not in _SUPPORTED_COUNTRIES:
            errors.append(ContractError(
                path="seller.country",
                message=f"only DE is supported in v1, got '{country}'",
                expected="DE",
                actual=country,
            ))

    # --- Buyer ---
    buyer = data.get("buyer")
    if not isinstance(buyer, dict):
        errors.append(ContractError(
            path="buyer", message="required object", expected="object", actual="missing",
        ))
    else:
        if not buyer.get("name"):
            errors.append(ContractError(
                path="buyer.name", message="required for EN 16931",
                expected="string", actual="missing",
            ))

    # --- Items ---
    items = data.get("items")
    if not isinstance(items, list) or not items:
        errors.append(ContractError(
            path="items", message="at least one line item required",
            expected="list", actual="missing" if items is None else "empty",
        ))
    else:
        tax_rates = set()
        for i, item in enumerate(items):
            if not isinstance(item, dict):
                errors.append(ContractError(
                    path=f"items[{i}]", message="must be an object",
                    expected="object", actual=type(item).__name__,
                ))
                continue
            for field in ("description", "quantity", "unit_price", "tax_rate", "line_total"):
                if field not in item:
                    errors.append(ContractError(
                        path=f"items[{i}].{field}",
                        message=f"required for EN 16931",
                        expected="number" if field != "description" else "string",
                        actual="missing",
                    ))
            if "tax_rate" in item:
                tax_rates.add(item["tax_rate"])

        # Fail on mixed tax rates (unsupported in v1)
        if len(tax_rates) > 1:
            errors.append(ContractError(
                path="items",
                message=f"mixed tax rates not supported in v1 (found: {sorted(tax_rates)})",
                expected="single tax rate",
                actual=f"{len(tax_rates)} rates",
            ))

    # --- Tax entries ---
    tax_entries = data.get("tax_entries")
    if not isinstance(tax_entries, list) or not tax_entries:
        errors.append(ContractError(
            path="tax_entries", message="at least one tax entry required",
            expected="list", actual="missing",
        ))

    # --- Totals ---
    for field in ("subtotal", "tax_total", "total"):
        val = data.get(field)
        if val is None or not isinstance(val, (int, float)):
            errors.append(ContractError(
                path=field,
                message=f"required numeric value for EN 16931",
                expected="number",
                actual="missing" if val is None else type(val).__name__,
            ))

    # --- Payment ---
    payment = data.get("payment")
    if not isinstance(payment, dict):
        errors.append(ContractError(
            path="payment", message="payment details required for EN 16931",
            expected="object", actual="missing",
        ))
    else:
        means = payment.get("means", "")
        if means and means not in _PAYMENT_MEANS_CODES:
            errors.append(ContractError(
                path="payment.means",
                message=f"unsupported payment means: '{means}'",
                expected=f"one of {list(_PAYMENT_MEANS_CODES.keys())}",
                actual=means,
            ))
        if means == "credit_transfer" and not payment.get("iban"):
            errors.append(ContractError(
                path="payment.iban",
                message="IBAN required for credit transfer",
                expected="string",
                actual="missing",
            ))

    # --- Unsupported features: fail loudly ---
    # Allowances and charges are hardcoded to zero in XML generation.
    # If data contains these fields, the visual PDF could show them but the
    # embedded XML would disagree — a compliance failure.  Reject early.
    for field in ("allowances", "charges", "discounts"):
        if data.get(field):
            errors.append(ContractError(
                path=field,
                message=f"allowances/charges/discounts not supported in v1 (field '{field}' present)",
                expected="absent or empty",
                actual=f"{len(data[field])} entries" if isinstance(data[field], list) else "present",
            ))

    # --- XRechnung-specific requirements ---
    if profile == "xrechnung":
        if not data.get("buyer_reference"):
            errors.append(ContractError(
                path="buyer_reference",
                message="Leitweg-ID (buyer_reference) required for XRechnung",
                expected="string",
                actual="missing",
            ))
        seller = data.get("seller", {})
        if not seller.get("contact_name"):
            errors.append(ContractError(
                path="seller.contact_name",
                message="seller contact person name required for XRechnung (BR-DE-5)",
                expected="string",
                actual="missing",
            ))
        if not seller.get("email"):
            errors.append(ContractError(
                path="seller.email",
                message="seller electronic address required for XRechnung",
                expected="string",
                actual="missing",
            ))

    return errors


# ---------------------------------------------------------------------------
# XML generation
# ---------------------------------------------------------------------------

def _parse_date(date_str: str) -> datetime.date:
    """Parse an ISO date string (YYYY-MM-DD) to a date object."""
    return datetime.date.fromisoformat(date_str)


_GUIDELINE_IDS = {
    "en16931": "urn:cen.eu:en16931:2017",
    "xrechnung": "urn:cen.eu:en16931:2017#compliant#urn:xeinkauf.de:kosit:xrechnung_3.0",
}


def build_invoice_xml(data: dict, *, profile: str = "en16931") -> bytes:
    """Convert Formforge invoice data dict to CII XML bytes.

    Uses ``drafthorse`` to build a UN/CEFACT Cross Industry Invoice
    document conforming to EN 16931 or XRechnung.

    Args:
        data: Invoice data dict matching the einvoice_data.json schema.
        profile: ``"en16931"`` (default) or ``"xrechnung"``.

    Returns:
        UTF-8 encoded CII XML bytes.

    Raises:
        ValueError: If data is invalid or XML generation fails.
    """
    doc = Document()

    # --- Context: guideline ---
    doc.context.guideline_parameter.id = _GUIDELINE_IDS[profile]

    # XRechnung requires a business process
    if profile == "xrechnung":
        doc.context.business_parameter.id = "urn:fdc:peppol.eu:2017:poacc:billing:01:1.0"

    # --- Header ---
    doc.header.id = data["invoice_number"]
    doc.header.type_code = "380"  # Invoice
    doc.header.issue_date_time = _parse_date(data["invoice_date"])

    # --- Seller ---
    seller_data = data["seller"]
    seller = doc.trade.agreement.seller
    seller.name = seller_data["name"]
    seller.address.line_one = seller_data["address"]
    seller.address.city_name = seller_data["city"]
    seller.address.postcode = seller_data["postal_code"]
    seller.address.country_id = seller_data["country"]
    seller.tax_registrations.add(
        TaxRegistration(id=("VA", seller_data["vat_id"]))
    )
    # Contact details (EXTENDED profile only — optional for EN 16931)
    if seller_data.get("email"):
        seller.contact.email.address = seller_data["email"]
    if seller_data.get("phone"):
        seller.contact.telephone.number = seller_data["phone"]

    # --- Buyer ---
    buyer_data = data["buyer"]
    buyer = doc.trade.agreement.buyer
    buyer.name = buyer_data["name"]
    if buyer_data.get("address"):
        buyer.address.line_one = buyer_data["address"]
    if buyer_data.get("city"):
        buyer.address.city_name = buyer_data["city"]
    if buyer_data.get("postal_code"):
        buyer.address.postcode = buyer_data["postal_code"]
    if buyer_data.get("country"):
        buyer.address.country_id = buyer_data["country"]

    # --- XRechnung-specific fields ---
    if profile == "xrechnung":
        # BT-10 Buyer Reference (Leitweg-ID for routing)
        if data.get("buyer_reference"):
            doc.trade.agreement.buyer_reference = data["buyer_reference"]
        # BT-34 Seller electronic address (tuple: scheme_id, value)
        if seller_data.get("email"):
            seller.electronic_address.uri_ID = ("EM", seller_data["email"])
        # BT-49 Buyer electronic address
        if buyer_data.get("email"):
            buyer.electronic_address.uri_ID = ("EM", buyer_data["email"])
        # BT-41 Seller contact person name (required by BR-DE-5)
        if seller_data.get("contact_name"):
            seller.contact.person_name = seller_data["contact_name"]

    # --- Line items ---
    for i, item in enumerate(data["items"]):
        li = LineItem()
        li.document.line_id = str(i + 1)
        li.product.name = item["description"]
        li.agreement.net.amount = Decimal(str(item["unit_price"]))
        li.agreement.net.basis_quantity = (Decimal("1.0000"), item.get("unit", "C62"))
        li.delivery.billed_quantity = (
            Decimal(str(item["quantity"])),
            item.get("unit", "C62"),
        )
        li.settlement.trade_tax.type_code = "VAT"
        li.settlement.trade_tax.category_code = "S"  # Standard rate
        li.settlement.trade_tax.rate_applicable_percent = Decimal(str(item["tax_rate"]))
        li.settlement.monetary_summation.total_amount = Decimal(str(item["line_total"]))
        doc.trade.items.add(li)

    # --- Delivery ---
    # BT-72 actual delivery date (required for EN 16931 unless invoicing period used)
    doc.trade.delivery.event.occurrence = _parse_date(data["invoice_date"])
    # BT-80 country of delivery (+ city/postcode for XRechnung BR-DE-10/BR-DE-11)
    doc.trade.delivery.ship_to.address.country_id = buyer_data.get("country", seller_data["country"])
    if buyer_data.get("city"):
        doc.trade.delivery.ship_to.address.city_name = buyer_data["city"]
    if buyer_data.get("postal_code"):
        doc.trade.delivery.ship_to.address.postcode = buyer_data["postal_code"]

    # --- Settlement ---
    settlement = doc.trade.settlement
    settlement.currency_code = data["currency"]

    # Payment means
    payment = data["payment"]
    pm = PaymentMeans()
    pm.type_code = _PAYMENT_MEANS_CODES.get(payment["means"], "58")
    if payment.get("iban"):
        pm.payee_account.iban = payment["iban"]
    if payment.get("bic"):
        pm.payee_institution.bic = payment["bic"]
    settlement.payment_means.add(pm)

    # Payment terms
    terms = PaymentTerms()
    if data.get("notes"):
        terms.description = data["notes"]
    terms.due = _parse_date(data["due_date"])
    settlement.terms.add(terms)

    # Tax summary
    for entry in data["tax_entries"]:
        tax = ApplicableTradeTax()
        tax.calculated_amount = Decimal(str(entry["amount"]))
        tax.type_code = "VAT"
        tax.basis_amount = Decimal(str(entry["basis"]))
        tax.category_code = "S"  # Standard rate
        tax.rate_applicable_percent = Decimal(str(entry["rate"]))
        settlement.trade_tax.add(tax)

    # Monetary summation
    ms = settlement.monetary_summation
    ms.line_total = Decimal(str(data["subtotal"]))
    ms.charge_total = Decimal("0.00")
    ms.allowance_total = Decimal("0.00")
    ms.tax_basis_total = Decimal(str(data["subtotal"]))
    ms.tax_total = (Decimal(str(data["tax_total"])), data["currency"])
    ms.grand_total = Decimal(str(data["total"]))
    ms.due_amount = Decimal(str(data["total"]))

    return doc.serialize(schema="FACTUR-X_EN16931")


# ---------------------------------------------------------------------------
# PDF post-processing
# ---------------------------------------------------------------------------

def apply_zugferd(pdf_bytes: bytes, xml_bytes: bytes, *, lang: str = "de") -> bytes:
    """Combine a visual PDF with CII XML into a ZUGFeRD PDF/A-3b document.

    Uses ``drafthorse.pdf.attach_xml`` to:
    - Embed the XML as an Associated File
    - Set PDF/A-3b markers
    - Add ZUGFeRD XMP metadata (fx: namespace)
    - Set output intents

    Args:
        pdf_bytes: Visual PDF rendered by Typst.
        xml_bytes: CII XML from ``build_invoice_xml()``.
        lang: RFC 3066 language code (default: "de").

    Returns:
        ZUGFeRD-compliant PDF/A-3b bytes.
    """
    return attach_xml(pdf_bytes, xml_bytes, level="EN 16931", lang=lang)
