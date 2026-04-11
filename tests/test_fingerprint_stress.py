"""Stress tests for input fingerprinting — edge cases, boundaries, adversarial inputs."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest

from formforge.fingerprint import (
    ChangeSet,
    FieldChange,
    FileChange,
    FileHash,
    InputFingerprint,
    _diff_dicts,
    _diff_lists,
    _discover_assets,
    _discover_includes,
    _hash_bytes,
    _truncate,
    compare,
    compute_fingerprint,
)

EXAMPLES = Path(__file__).parent.parent / "examples"
FIXTURES = Path(__file__).parent / "fixtures"


def _load_data(name: str = "invoice_data.json") -> dict:
    return json.loads((EXAMPLES / name).read_text())


# ---------------------------------------------------------------------------
# Empty / minimal inputs
# ---------------------------------------------------------------------------

class TestEmptyInputs:
    def test_empty_data_dict(self):
        """Empty data should still fingerprint."""
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", {})
        assert fp.data_hash.startswith("sha256:")
        assert fp.fingerprint.startswith("sha256:")

    def test_minimal_data(self):
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", {"x": 1})
        assert fp.data_hash.startswith("sha256:")

    def test_raw_typ_template(self):
        """Raw .typ (no Jinja2) should work — no includes or assets from scanning."""
        if FIXTURES.exists() and (FIXTURES / "simple.typ").exists():
            fp = compute_fingerprint(FIXTURES / "simple.typ", {})
            assert fp.include_hashes == ()  # No includes for raw .typ

    def test_no_font_paths(self):
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", {}, font_paths=None)
        assert fp.font_hashes == ()

    def test_empty_font_paths(self):
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", {}, font_paths=[])
        assert fp.font_hashes == ()


# ---------------------------------------------------------------------------
# Non-ASCII and special characters
# ---------------------------------------------------------------------------

class TestUnicodeData:
    def test_unicode_values(self):
        data = {
            "name": "Ünîcödé Cörp — «Société»",
            "address": "日本語テスト",
            "amount": "€1.234,56",
            "emoji": "🏢📧",
        }
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        assert fp.data_hash.startswith("sha256:")

    def test_unicode_deterministic(self):
        data = {"field": "Ünîcödé — «»"}
        fp1 = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        fp2 = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        assert fp1.data_hash == fp2.data_hash

    def test_null_values_in_data(self):
        data = {"field": None, "nested": {"also_null": None}}
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        assert fp.data_hash.startswith("sha256:")


# ---------------------------------------------------------------------------
# Large payloads
# ---------------------------------------------------------------------------

class TestLargePayloads:
    def test_many_items(self):
        """10,000 line items should fingerprint without issue."""
        items = [
            {"num": i, "desc": f"Item {i}", "qty": i, "price": i * 10.5}
            for i in range(10_000)
        ]
        data = {"items": items, "subtotal": sum(i["price"] for i in items)}
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        assert fp.data_hash.startswith("sha256:")

    def test_large_string_value(self):
        """A 1MB string value in data."""
        data = {"notes": "x" * 1_000_000}
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        assert fp.data_hash.startswith("sha256:")

    def test_deeply_nested(self):
        """10 levels of nesting."""
        data: dict = {"level": 0}
        current = data
        for i in range(1, 10):
            current["child"] = {"level": i}
            current = current["child"]
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        assert fp.data_hash.startswith("sha256:")


# ---------------------------------------------------------------------------
# Data diff edge cases
# ---------------------------------------------------------------------------

class TestDiffEdgeCases:
    def test_diff_empty_to_populated(self):
        changes = _diff_dicts({}, {"a": 1, "b": "two"})
        assert len(changes) == 2
        assert all(c.change_type == "added" for c in changes)

    def test_diff_populated_to_empty(self):
        changes = _diff_dicts({"a": 1, "b": "two"}, {})
        assert len(changes) == 2
        assert all(c.change_type == "removed" for c in changes)

    def test_diff_both_empty(self):
        changes = _diff_dicts({}, {})
        assert len(changes) == 0

    def test_diff_type_change(self):
        """Value changes from string to int."""
        changes = _diff_dicts({"x": "5"}, {"x": 5})
        assert len(changes) == 1
        assert changes[0].change_type == "modified"

    def test_diff_list_grow(self):
        changes = _diff_lists([1, 2], [1, 2, 3, 4], "items")
        assert len(changes) == 2
        assert all(c.change_type == "added" for c in changes)

    def test_diff_list_shrink(self):
        changes = _diff_lists([1, 2, 3, 4], [1, 2], "items")
        assert len(changes) == 2
        assert all(c.change_type == "removed" for c in changes)

    def test_diff_list_empty_to_populated(self):
        changes = _diff_lists([], [1, 2, 3], "items")
        assert len(changes) == 3

    def test_diff_nested_list_of_dicts(self):
        old = [{"a": 1}, {"a": 2}]
        new = [{"a": 1}, {"a": 99}]
        changes = _diff_lists(old, new, "items")
        assert len(changes) == 1
        assert changes[0].path == "items[1].a"

    def test_diff_mixed_types_in_list(self):
        """List contains both dicts and scalars."""
        old = [1, {"a": 2}]
        new = [1, {"a": 3}]
        changes = _diff_lists(old, new, "items")
        assert len(changes) == 1
        assert changes[0].path == "items[1].a"

    def test_diff_bool_change(self):
        changes = _diff_dicts({"flag": True}, {"flag": False})
        assert len(changes) == 1

    def test_diff_none_to_value(self):
        changes = _diff_dicts({"x": None}, {"x": "hello"})
        assert len(changes) == 1
        assert changes[0].change_type == "modified"

    def test_diff_preserves_path_prefix(self):
        changes = _diff_dicts(
            {"a": {"b": {"c": 1}}},
            {"a": {"b": {"c": 2}}},
        )
        assert changes[0].path == "a.b.c"


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------

class TestTruncation:
    def test_short_value_not_truncated(self):
        assert _truncate("hello") == '"hello"'

    def test_long_value_truncated(self):
        result = _truncate("x" * 500)
        assert len(result) <= 200
        assert result.endswith("...")

    def test_dict_truncated(self):
        result = _truncate({"a": "x" * 500})
        assert len(result) <= 200

    def test_non_serializable(self):
        """Objects that can't be JSON-serialized use str()."""
        result = _truncate(object())
        assert len(result) > 0


# ---------------------------------------------------------------------------
# File discovery edge cases
# ---------------------------------------------------------------------------

class TestFileDiscovery:
    def test_discover_includes_on_raw_typ(self, tmp_path):
        """Raw .typ should return no includes."""
        typ_file = tmp_path / "test.typ"
        typ_file.write_text("Hello world")
        assert _discover_includes(typ_file) == []

    def test_discover_includes_missing_fragment(self, tmp_path):
        """Include pointing to nonexistent file should be skipped."""
        template = tmp_path / "test.j2.typ"
        template.write_text('{% include "nonexistent.j2.typ" %}')
        includes = _discover_includes(template)
        assert len(includes) == 0

    def test_discover_assets_jinja_variable(self, tmp_path):
        """image() with Jinja2 variable should be skipped."""
        template = tmp_path / "test.j2.typ"
        template.write_text('image("{{ logo_path }}")')
        assets = _discover_assets(template)
        assert len(assets) == 0

    def test_discover_assets_missing_file(self, tmp_path):
        """image() pointing to nonexistent file should be skipped."""
        template = tmp_path / "test.j2.typ"
        template.write_text('image("nonexistent.png")')
        assets = _discover_assets(template)
        assert len(assets) == 0

    def test_discover_assets_real_file(self, tmp_path):
        logo = tmp_path / "logo.png"
        logo.write_bytes(b"\x89PNG\r\n")
        template = tmp_path / "test.j2.typ"
        template.write_text('image("logo.png")')
        assets = _discover_assets(template)
        assert len(assets) == 1


# ---------------------------------------------------------------------------
# Fingerprint serialization edge cases
# ---------------------------------------------------------------------------

class TestSerializationEdgeCases:
    def test_from_dict_missing_optional(self):
        """zugferd_profile=None should round-trip."""
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", {})
        d = fp.to_dict()
        assert d["zugferd_profile"] is None
        fp2 = InputFingerprint.from_dict(d)
        assert fp2.zugferd_profile is None

    def test_from_dict_with_zugferd(self):
        fp = compute_fingerprint(
            EXAMPLES / "invoice.j2.typ", {},
            zugferd_profile="en16931",
        )
        d = fp.to_dict()
        fp2 = InputFingerprint.from_dict(d)
        assert fp2.zugferd_profile == "en16931"

    def test_changeset_to_dict_empty(self):
        cs = ChangeSet(baseline_fingerprint="a", current_fingerprint="b")
        d = cs.to_dict()
        assert d["data_changes"] == []
        assert d["template_changes"] == []


# ---------------------------------------------------------------------------
# Compare edge cases
# ---------------------------------------------------------------------------

class TestCompareEdgeCases:
    def test_compare_same_object(self):
        fp = compute_fingerprint(EXAMPLES / "invoice.j2.typ", {})
        cs = compare(fp, fp, {}, {})
        assert not cs.has_changes

    def test_compare_all_config_changed(self):
        data = _load_data()
        fp1 = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data)
        fp2 = compute_fingerprint(
            EXAMPLES / "invoice.j2.typ", data,
            zugferd_profile="en16931",
            provenance_enabled=True,
            validate_enabled=True,
        )
        cs = compare(fp1, fp2, data, data)
        assert "config" in cs.change_categories
        config_keys = [c.key for c in cs.config_changes]
        assert "zugferd_profile" in config_keys
        assert "provenance_enabled" in config_keys
        assert "validate_enabled" in config_keys

    def test_changeset_categories_accumulate(self):
        data1 = _load_data()
        data2 = _load_data()
        data2["invoice_number"] = "CHANGED"
        fp1 = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data1)
        fp2 = compute_fingerprint(
            EXAMPLES / "invoice.j2.typ", data2,
            zugferd_profile="en16931",
        )
        cs = compare(fp1, fp2, data1, data2)
        cats = cs.change_categories
        assert "data" in cats
        assert "config" in cats


# ---------------------------------------------------------------------------
# Hashing consistency
# ---------------------------------------------------------------------------

class TestHashingConsistency:
    def test_hash_bytes_deterministic(self):
        h1 = _hash_bytes(b"test data")
        h2 = _hash_bytes(b"test data")
        assert h1 == h2

    def test_hash_bytes_different_content(self):
        h1 = _hash_bytes(b"data1")
        h2 = _hash_bytes(b"data2")
        assert h1 != h2

    def test_canonical_json_key_order(self):
        """Key order should not affect data hash."""
        data1 = {"b": 2, "a": 1}
        data2 = {"a": 1, "b": 2}
        fp1 = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data1)
        fp2 = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data2)
        assert fp1.data_hash == fp2.data_hash

    def test_whitespace_in_json_not_significant(self):
        """Canonical JSON strips whitespace, so hashes should match."""
        data1 = {"key": "value"}
        data2 = {"key": "value"}
        fp1 = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data1)
        fp2 = compute_fingerprint(EXAMPLES / "invoice.j2.typ", data2)
        assert fp1.data_hash == fp2.data_hash


# ---------------------------------------------------------------------------
# All example templates
# ---------------------------------------------------------------------------

class TestAllExampleTemplates:
    """Fingerprint every example template to ensure no crashes."""

    @pytest.mark.parametrize("template,data_file", [
        ("invoice.j2.typ", "invoice_data.json"),
        ("statement.j2.typ", "statement_data.json"),
        ("receipt.j2.typ", "receipt_data.json"),
        ("letter.j2.typ", "letter_data.json"),
        ("report.j2.typ", "report_data.json"),
    ])
    def test_example_fingerprints(self, template, data_file):
        template_path = EXAMPLES / template
        if not template_path.exists():
            pytest.skip(f"Template {template} not found")
        data = json.loads((EXAMPLES / data_file).read_text())
        fp = compute_fingerprint(template_path, data)
        assert fp.fingerprint.startswith("sha256:")
        assert fp.template_hash.size > 0
