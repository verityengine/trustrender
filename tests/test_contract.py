"""Tests for data-contract inference and validation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from trustrender.contract import (
    LIST_OBJECT,
    LIST_SCALAR,
    OBJECT,
    SCALAR,
    infer_contract,
    validate_data,
)
from trustrender.errors import ErrorCode, TrustRenderError

EXAMPLES = Path(__file__).parent.parent / "examples"


def _load_data(name: str) -> dict:
    return json.loads((EXAMPLES / f"{name}_data.json").read_text())


# -----------------------------------------------------------------------
# Schema inference — per template
# -----------------------------------------------------------------------


class TestInferInvoice:
    def setup_method(self):
        self.contract = infer_contract(EXAMPLES / "invoice.j2.typ")

    def test_top_level_scalars(self):
        for name in [
            "invoice_number",
            "invoice_date",
            "due_date",
            "payment_terms",
            "subtotal",
            "tax_rate",
            "tax_amount",
            "total",
        ]:
            assert name in self.contract
            assert self.contract[name].expected_type == SCALAR
            assert self.contract[name].required is True

    def test_sender_is_object(self):
        sender = self.contract["sender"]
        assert sender.expected_type == OBJECT
        assert sender.required is True
        assert set(sender.children.keys()) == {
            "name",
            "address",
            "email",
        }

    def test_recipient_is_object(self):
        recipient = self.contract["recipient"]
        assert recipient.expected_type == OBJECT
        assert set(recipient.children.keys()) == {
            "name",
            "address",
            "email",
        }

    def test_items_is_list_object(self):
        items = self.contract["items"]
        assert items.expected_type == LIST_OBJECT
        assert items.required is True
        assert set(items.children.keys()) == {
            "num",
            "description",
            "qty",
            "unit_price",
            "amount",
        }

    def test_set_vars_excluded(self):
        """{% set %} variables like logo_path, doc_title should not appear."""
        for name in ["logo_path", "doc_title", "doc_subtitle"]:
            assert name not in self.contract

    def test_notes_is_required(self):
        """notes is used unconditionally in invoice template."""
        assert self.contract["notes"].required is True


class TestInferStatement:
    def setup_method(self):
        self.contract = infer_contract(EXAMPLES / "statement.j2.typ")

    def test_transactions_is_list_object(self):
        txns = self.contract["transactions"]
        assert txns.expected_type == LIST_OBJECT
        assert set(txns.children.keys()) == {
            "date",
            "reference",
            "description",
            "amount",
            "balance",
        }

    def test_aging_is_object(self):
        aging = self.contract["aging"]
        assert aging.expected_type == OBJECT
        assert set(aging.children.keys()) == {
            "current",
            "days_30",
            "days_60",
            "days_90",
            "total",
        }

    def test_startswith_not_a_child(self):
        """txn.amount.startswith() should not add startswith as a field."""
        txns = self.contract["transactions"]
        assert "startswith" not in txns.children
        # amount should be there as a real field.
        assert "amount" in txns.children


class TestInferReceipt:
    def setup_method(self):
        self.contract = infer_contract(EXAMPLES / "receipt.j2.typ")

    def test_payment_is_object(self):
        payment = self.contract["payment"]
        assert payment.expected_type == OBJECT
        assert set(payment.children.keys()) == {
            "method",
            "last_four",
            "auth_code",
        }

    def test_change_due_required(self):
        """change_due in {% if change_due != "$0.00" %} is required (comparison)."""
        assert self.contract["change_due"].required is True


class TestInferLetter:
    def setup_method(self):
        self.contract = infer_contract(EXAMPLES / "letter.j2.typ")

    def test_body_paragraphs_is_list_scalar(self):
        bp = self.contract["body_paragraphs"]
        assert bp.expected_type == LIST_SCALAR
        assert bp.required is True

    def test_enclosures_optional(self):
        """enclosures guarded by {% if enclosures %} — optional."""
        enc = self.contract["enclosures"]
        assert enc.expected_type == LIST_SCALAR
        assert enc.required is False

    def test_cc_optional(self):
        """cc guarded by {% if cc %} — optional."""
        cc = self.contract["cc"]
        assert cc.expected_type == LIST_SCALAR
        assert cc.required is False

    def test_loop_var_not_in_contract(self):
        """Loop variables like paragraph, enc, person should not appear."""
        for name in ["paragraph", "enc", "person"]:
            assert name not in self.contract

    def test_sender_has_phone(self):
        """Letter template accesses sender.phone unlike invoice."""
        assert "phone" in self.contract["sender"].children


class TestInferReport:
    def setup_method(self):
        self.contract = infer_contract(EXAMPLES / "report.j2.typ")

    def test_metrics_is_list_object(self):
        metrics = self.contract["metrics"]
        assert metrics.expected_type == LIST_OBJECT
        assert set(metrics.children.keys()) == {
            "label",
            "value",
            "target",
            "status",
        }

    def test_incidents_is_list_object(self):
        inc = self.contract["incidents"]
        assert inc.expected_type == LIST_OBJECT
        assert set(inc.children.keys()) == {
            "id",
            "severity",
            "date",
            "duration",
            "description",
            "root_cause",
            "resolution",
        }

    def test_spend_by_service_no_startswith(self):
        """s.change.startswith() should not add startswith as field."""
        sbs = self.contract["spend_by_service"]
        assert "startswith" not in sbs.children
        assert "change" in sbs.children

    def test_recommendations_is_list_scalar(self):
        recs = self.contract["recommendations"]
        assert recs.expected_type == LIST_SCALAR
        assert recs.required is True


# -----------------------------------------------------------------------
# Validation — all templates pass with real data
# -----------------------------------------------------------------------


class TestValidationPass:
    @pytest.mark.parametrize(
        "name",
        [
            "invoice",
            "statement",
            "receipt",
            "letter",
            "report",
        ],
    )
    def test_real_data_passes(self, name):
        contract = infer_contract(EXAMPLES / f"{name}.j2.typ")
        data = _load_data(name)
        errors = validate_data(contract, data)
        assert errors == [], f"Unexpected errors: {errors}"


# -----------------------------------------------------------------------
# Validation — failures
# -----------------------------------------------------------------------


class TestValidationMissingFields:
    def test_missing_top_level(self):
        contract = infer_contract(EXAMPLES / "invoice.j2.typ")
        data = _load_data("invoice")
        del data["invoice_number"]
        errors = validate_data(contract, data)
        paths = [e.path for e in errors]
        assert "invoice_number" in paths

    def test_missing_nested(self):
        contract = infer_contract(EXAMPLES / "invoice.j2.typ")
        data = _load_data("invoice")
        del data["sender"]["name"]
        errors = validate_data(contract, data)
        paths = [e.path for e in errors]
        assert "sender.name" in paths

    def test_missing_list_item_field(self):
        contract = infer_contract(EXAMPLES / "invoice.j2.typ")
        data = _load_data("invoice")
        del data["items"][2]["description"]
        errors = validate_data(contract, data)
        paths = [e.path for e in errors]
        assert "items[2].description" in paths

    def test_empty_data(self):
        contract = infer_contract(EXAMPLES / "invoice.j2.typ")
        errors = validate_data(contract, {})
        # All required top-level fields should be reported.
        paths = {e.path for e in errors}
        assert "sender" in paths
        assert "recipient" in paths
        assert "invoice_number" in paths
        assert "items" in paths


class TestValidationTypeMismatch:
    def test_scalar_where_object_expected(self):
        contract = infer_contract(EXAMPLES / "invoice.j2.typ")
        data = _load_data("invoice")
        data["sender"] = "not an object"
        errors = validate_data(contract, data)
        assert len(errors) == 1
        assert errors[0].path == "sender"
        assert errors[0].expected == "object"
        assert errors[0].actual == "string"

    def test_scalar_where_list_expected(self):
        contract = infer_contract(EXAMPLES / "invoice.j2.typ")
        data = _load_data("invoice")
        data["items"] = "not a list"
        errors = validate_data(contract, data)
        assert len(errors) == 1
        assert errors[0].path == "items"
        assert errors[0].expected == "list"

    def test_list_where_object_expected(self):
        contract = infer_contract(EXAMPLES / "invoice.j2.typ")
        data = _load_data("invoice")
        data["sender"] = [1, 2, 3]
        errors = validate_data(contract, data)
        assert len(errors) == 1
        assert errors[0].path == "sender"
        assert errors[0].expected == "object"
        assert errors[0].actual == "list"

    def test_dict_where_scalar_expected(self):
        contract = infer_contract(EXAMPLES / "invoice.j2.typ")
        data = _load_data("invoice")
        data["invoice_number"] = {"nested": "object"}
        errors = validate_data(contract, data)
        assert len(errors) == 1
        assert errors[0].path == "invoice_number"
        assert errors[0].expected == "scalar"
        assert errors[0].actual == "object"


class TestValidationNull:
    def test_null_required_field(self):
        contract = infer_contract(EXAMPLES / "invoice.j2.typ")
        data = _load_data("invoice")
        data["subtotal"] = None
        errors = validate_data(contract, data)
        paths = [e.path for e in errors]
        assert "subtotal" in paths
        err = [e for e in errors if e.path == "subtotal"][0]
        assert err.actual == "null"

    def test_null_in_list_item(self):
        contract = infer_contract(EXAMPLES / "invoice.j2.typ")
        data = _load_data("invoice")
        data["items"][0]["amount"] = None
        errors = validate_data(contract, data)
        paths = [e.path for e in errors]
        assert "items[0].amount" in paths


class TestValidationConditional:
    def test_optional_field_missing_is_ok(self):
        """Missing an optional field (enclosures) should not error."""
        contract = infer_contract(EXAMPLES / "letter.j2.typ")
        data = _load_data("letter")
        del data["enclosures"]
        errors = validate_data(contract, data)
        paths = [e.path for e in errors]
        assert "enclosures" not in paths

    def test_optional_field_present_wrong_type(self):
        """Optional field present but wrong type should still error."""
        contract = infer_contract(EXAMPLES / "letter.j2.typ")
        data = _load_data("letter")
        data["enclosures"] = "not a list"
        errors = validate_data(contract, data)
        paths = [e.path for e in errors]
        assert "enclosures" in paths


class TestValidationExtraFields:
    def test_extra_fields_allowed(self):
        """Extra unexpected fields in data should not cause errors."""
        contract = infer_contract(EXAMPLES / "invoice.j2.typ")
        data = _load_data("invoice")
        data["completely_unknown_field"] = "hello"
        data["another_extra"] = {"nested": True}
        data["sender"]["bonus_field"] = "extra"
        errors = validate_data(contract, data)
        assert errors == []


class TestValidationGuardMerge:
    def test_field_guarded_and_unguarded_stays_required(self):
        """If a field appears both inside and outside a guard, it's required."""
        # notes in invoice is used unconditionally -> required
        contract = infer_contract(EXAMPLES / "invoice.j2.typ")
        assert contract["notes"].required is True

        # change_due in receipt is in a comparison guard -> required
        contract2 = infer_contract(EXAMPLES / "receipt.j2.typ")
        assert contract2["change_due"].required is True


# -----------------------------------------------------------------------
# Include-aware inference
# -----------------------------------------------------------------------


class TestIncludeInference:
    """Contract inference follows {% include %} fragments."""

    def test_static_include_with_data_field(self, tmp_path):
        """Fragment that accesses a data field adds it to the contract."""
        # Create a fragment that references a real data field.
        frag_dir = tmp_path / "fragments"
        frag_dir.mkdir()
        (frag_dir / "header.j2.typ").write_text("{{ company_name }}")

        # Main template includes the fragment.
        (tmp_path / "main.j2.typ").write_text(
            '{% include "fragments/header.j2.typ" %}\n{{ title }}'
        )

        contract = infer_contract(tmp_path / "main.j2.typ")
        assert "title" in contract
        assert "company_name" in contract  # From the included fragment

    def test_include_set_variable_not_in_contract(self):
        """Fragment accessing parent's {% set %} var does not create contract field."""
        # invoice.j2.typ sets logo_path, doc_title, doc_subtitle before include.
        # The included header_logo.j2.typ uses those vars.
        # They should NOT appear in the contract.
        contract = infer_contract(EXAMPLES / "invoice.j2.typ")
        assert "logo_path" not in contract
        assert "doc_title" not in contract
        assert "doc_subtitle" not in contract

    def test_include_without_context(self, tmp_path):
        """{% include ... without context %} fragment cannot see parent locals."""
        frag_dir = tmp_path / "fragments"
        frag_dir.mkdir()
        # Fragment references a variable that parent set via {% set %}.
        (frag_dir / "frag.j2.typ").write_text("{{ local_var }}")

        # Parent sets local_var then includes without context.
        (tmp_path / "main.j2.typ").write_text(
            '{% set local_var = "x" %}\n'
            '{% include "fragments/frag.j2.typ" without context %}'
        )

        contract = infer_contract(tmp_path / "main.j2.typ")
        # Without context: fragment's local_var is NOT the parent's set var,
        # so it becomes a contract field.
        assert "local_var" in contract

    def test_circular_include_no_crash(self, tmp_path):
        """Circular includes do not cause infinite recursion."""
        (tmp_path / "a.j2.typ").write_text(
            '{% include "b.j2.typ" %}\n{{ field_a }}'
        )
        (tmp_path / "b.j2.typ").write_text(
            '{% include "a.j2.typ" %}\n{{ field_b }}'
        )

        contract = infer_contract(tmp_path / "a.j2.typ")
        assert "field_a" in contract
        assert "field_b" in contract  # From b.j2.typ

    def test_dynamic_include_marks_partial(self, tmp_path):
        """{% include some_var %} marks the contract as partial."""
        from trustrender.contract import infer_contract_with_metadata

        (tmp_path / "main.j2.typ").write_text(
            "{% include template_name %}\n{{ title }}"
        )

        result = infer_contract_with_metadata(tmp_path / "main.j2.typ")
        assert result.is_partial is True
        assert "<dynamic>" in result.unresolved_includes
        assert "title" in result.contract

    def test_missing_fragment_marks_partial(self, tmp_path):
        """{% include 'nonexistent.j2.typ' %} marks partial, no crash."""
        from trustrender.contract import infer_contract_with_metadata

        (tmp_path / "main.j2.typ").write_text(
            '{% include "nonexistent.j2.typ" %}\n{{ title }}'
        )

        result = infer_contract_with_metadata(tmp_path / "main.j2.typ")
        assert result.is_partial is True
        assert "nonexistent.j2.typ" in result.unresolved_includes
        assert "title" in result.contract  # Rest of contract still works

    def test_ignore_missing_not_partial(self, tmp_path):
        """{% include 'x' ignore missing %} does not mark as partial."""
        from trustrender.contract import infer_contract_with_metadata

        (tmp_path / "main.j2.typ").write_text(
            '{% include "nonexistent.j2.typ" ignore missing %}\n{{ title }}'
        )

        result = infer_contract_with_metadata(tmp_path / "main.j2.typ")
        assert result.is_partial is False
        assert "title" in result.contract

    def test_nested_includes(self, tmp_path):
        """Includes within includes are followed."""
        frag_dir = tmp_path / "fragments"
        frag_dir.mkdir()
        (frag_dir / "inner.j2.typ").write_text("{{ deep_field }}")
        (frag_dir / "outer.j2.typ").write_text(
            '{% include "fragments/inner.j2.typ" %}\n{{ mid_field }}'
        )
        (tmp_path / "main.j2.typ").write_text(
            '{% include "fragments/outer.j2.typ" %}\n{{ top_field }}'
        )

        contract = infer_contract(tmp_path / "main.j2.typ")
        assert "top_field" in contract
        assert "mid_field" in contract
        assert "deep_field" in contract

    def test_existing_invoice_contract_unchanged(self):
        """Invoice contract is unchanged after include support."""
        contract = infer_contract(EXAMPLES / "invoice.j2.typ")
        # Same fields as before — includes only use {% set %} vars.
        expected = {
            "invoice_number", "invoice_date", "due_date", "payment_terms",
            "notes", "sender", "recipient", "items",
            "subtotal", "tax_rate", "tax_amount", "total",
        }
        assert set(contract.keys()) == expected

    def test_existing_statement_contract_unchanged(self):
        """Statement contract is unchanged after include support."""
        contract = infer_contract(EXAMPLES / "statement.j2.typ")
        expected = {
            "company", "customer", "statement_date", "period",
            "opening_balance", "closing_balance", "total_charges",
            "total_payments", "transactions", "aging", "notes",
        }
        assert set(contract.keys()) == expected


# -----------------------------------------------------------------------
# Integration — render() with bad data
# -----------------------------------------------------------------------


class TestIntegration:
    def test_render_bad_data_raises_data_contract(self):
        """render(validate=True) with incomplete data raises DATA_CONTRACT."""
        from trustrender import render

        with pytest.raises(TrustRenderError) as exc_info:
            render(EXAMPLES / "invoice.j2.typ", {}, validate=True)

        exc = exc_info.value
        assert exc.code == ErrorCode.DATA_CONTRACT
        assert exc.stage == "data_validation"

    def test_render_good_data_passes(self):
        """render(validate=True) with complete data should succeed."""
        from trustrender import render

        data = _load_data("invoice")
        pdf = render(EXAMPLES / "invoice.j2.typ", data, validate=True)
        assert pdf[:5] == b"%PDF-"

    def test_render_with_validate_false_skips_contract(self):
        """render(validate=False) skips contract validation."""
        from trustrender import render

        # Bad data with explicit validate=False — should hit Jinja error, not contract.
        with pytest.raises(TrustRenderError) as exc_info:
            render(EXAMPLES / "invoice.j2.typ", {"invoice_number": "X"}, validate=False)

        # Should be a template error, not DATA_CONTRACT.
        assert exc_info.value.code != ErrorCode.DATA_CONTRACT

    def test_validate_true_is_default(self):
        """render() validates by default for .j2.typ templates."""
        from trustrender import render

        # No validate= argument — default should be True
        with pytest.raises(TrustRenderError) as exc_info:
            render(EXAMPLES / "invoice.j2.typ", {"invoice_number": "X"})
        assert exc_info.value.code == ErrorCode.DATA_CONTRACT

    def test_error_detail_contains_paths(self):
        """Error detail should contain the missing field paths."""
        from trustrender import render

        with pytest.raises(TrustRenderError) as exc_info:
            render(
                EXAMPLES / "invoice.j2.typ",
                {"invoice_number": "X"},
                validate=True,
            )

        detail = exc_info.value.detail
        assert "sender" in detail
        assert "items" in detail
