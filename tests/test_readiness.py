"""Tests for pre-render readiness verification."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from formforge.readiness import preflight

EXAMPLES = Path(__file__).parent.parent / "examples"


def _load_data(name: str) -> dict:
    return json.loads((EXAMPLES / f"{name}_data.json").read_text())


class TestPreflightHappyPath:
    def test_invoice_passes(self):
        verdict = preflight(EXAMPLES / "invoice.j2.typ", _load_data("invoice"))
        assert verdict.ready is True
        assert len(verdict.errors) == 0

    def test_einvoice_passes(self):
        verdict = preflight(EXAMPLES / "einvoice.j2.typ", _load_data("einvoice"))
        assert verdict.ready is True

    def test_statement_passes(self):
        verdict = preflight(EXAMPLES / "statement.j2.typ", _load_data("statement"))
        assert verdict.ready is True

    def test_receipt_passes(self):
        verdict = preflight(EXAMPLES / "receipt.j2.typ", _load_data("receipt"))
        assert verdict.ready is True

    def test_letter_passes(self):
        verdict = preflight(EXAMPLES / "letter.j2.typ", _load_data("letter"))
        assert verdict.ready is True

    def test_report_passes(self):
        verdict = preflight(EXAMPLES / "report.j2.typ", _load_data("report"))
        assert verdict.ready is True


class TestPreflightPayload:
    def test_empty_data_fails(self):
        verdict = preflight(EXAMPLES / "invoice.j2.typ", {})
        assert verdict.ready is False
        assert len(verdict.errors) > 0
        assert all(e.stage == "payload" for e in verdict.errors)

    def test_missing_field_reported(self):
        data = _load_data("invoice")
        del data["sender"]
        verdict = preflight(EXAMPLES / "invoice.j2.typ", data)
        assert verdict.ready is False
        paths = [e.path for e in verdict.errors]
        assert "sender" in paths

    def test_extra_fields_allowed(self):
        data = _load_data("invoice")
        data["completely_unknown"] = "hello"
        verdict = preflight(EXAMPLES / "invoice.j2.typ", data)
        assert verdict.ready is True


class TestPreflightTemplate:
    def test_missing_template_fails(self):
        verdict = preflight("nonexistent.j2.typ", {})
        assert verdict.ready is False
        assert any(e.check == "template_not_found" for e in verdict.errors)

    def test_stages_tracked(self):
        verdict = preflight(EXAMPLES / "invoice.j2.typ", _load_data("invoice"))
        assert "payload" in verdict.stages_checked
        assert "template" in verdict.stages_checked
        assert "environment" in verdict.stages_checked


class TestPreflightCompliance:
    def test_en16931_eligible(self):
        verdict = preflight(
            EXAMPLES / "einvoice.j2.typ",
            _load_data("einvoice"),
            zugferd="en16931",
        )
        assert verdict.ready is True
        assert "en16931" in verdict.profile_eligible
        assert "compliance" in verdict.stages_checked

    def test_profile_eligibility_report(self):
        verdict = preflight(
            EXAMPLES / "einvoice.j2.typ",
            _load_data("einvoice"),
            zugferd="en16931",
        )
        assert "en16931" in verdict.profile_eligible

    def test_non_eur_currency_fails(self):
        data = _load_data("einvoice")
        data["currency"] = "USD"
        verdict = preflight(
            EXAMPLES / "einvoice.j2.typ", data, zugferd="en16931",
        )
        assert verdict.ready is False
        assert any("USD" in e.message for e in verdict.errors)


class TestPreflightEnvironment:
    def test_environment_checked(self):
        verdict = preflight(EXAMPLES / "invoice.j2.typ", _load_data("invoice"))
        assert "environment" in verdict.stages_checked


class TestPreflightFonts:
    """Font verification in preflight."""

    def test_bundled_template_with_fonts_passes(self):
        """Bundled templates pass font check when bundled fonts are available."""
        from formforge import _build_font_paths

        verdict = preflight(
            EXAMPLES / "invoice.j2.typ",
            _load_data("invoice"),
            font_paths=_build_font_paths(None),
        )
        assert verdict.ready is True
        font_issues = [i for i in verdict.errors + verdict.warnings if i.check == "missing_font"]
        assert len(font_issues) == 0

    def test_bundled_template_missing_inter_is_error(self):
        """Bundled template expecting Inter → error when Inter is missing."""
        verdict = preflight(
            EXAMPLES / "invoice.j2.typ",
            _load_data("invoice"),
            font_paths=["/nonexistent/empty/dir"],
        )
        assert verdict.ready is False
        font_errors = [i for i in verdict.errors if i.check == "missing_font"]
        assert len(font_errors) > 0
        assert any("Inter" in e.path for e in font_errors)

    def test_custom_template_missing_font_is_warning(self):
        """Custom template with unknown font → warning, not error."""
        fixtures = Path(__file__).parent / "fixtures"
        verdict = preflight(
            fixtures / "bad_font.j2.typ",
            {"title": "Test"},
            font_paths=["/nonexistent/empty/dir"],
        )
        # Missing font on custom template is a warning, not blocking
        assert verdict.ready is True
        font_warnings = [i for i in verdict.warnings if i.check == "missing_font"]
        assert len(font_warnings) > 0
        assert any("NonExistentFontFamilyXYZ123" in w.path for w in font_warnings)

    def test_strict_promotes_warning_to_error(self):
        """strict=True promotes custom-template font warnings to errors."""
        fixtures = Path(__file__).parent / "fixtures"
        verdict = preflight(
            fixtures / "bad_font.j2.typ",
            {"title": "Test"},
            font_paths=["/nonexistent/empty/dir"],
            strict=True,
        )
        assert verdict.ready is False
        font_errors = [i for i in verdict.errors if i.check == "missing_font"]
        assert len(font_errors) > 0

    def test_no_font_paths_warns_for_custom(self):
        """When font_paths is None, no available fonts to check against."""
        fixtures = Path(__file__).parent / "fixtures"
        verdict = preflight(
            fixtures / "bad_font.j2.typ",
            {"title": "Test"},
            font_paths=None,
        )
        font_issues = [i for i in verdict.warnings if i.check == "missing_font"]
        assert len(font_issues) > 0

    def test_template_without_font_declaration_passes(self):
        """Templates with no font declaration produce no font issues."""
        fixtures = Path(__file__).parent / "fixtures"
        # hello.typ has no font declaration
        hello = EXAMPLES / "hello.typ"
        if hello.exists():
            verdict = preflight(hello, {})
            font_issues = [i for i in verdict.errors + verdict.warnings if i.check == "missing_font"]
            assert len(font_issues) == 0

    def test_all_bundled_templates_pass_with_bundled_fonts(self):
        """All bundled templates pass font check with default font resolution."""
        from formforge import _build_font_paths

        font_paths = _build_font_paths(None)
        for name in ("invoice", "receipt", "statement", "letter", "report"):
            template = EXAMPLES / f"{name}.j2.typ"
            if template.exists():
                verdict = preflight(template, _load_data(name), font_paths=font_paths)
                font_issues = [i for i in verdict.errors if i.check == "missing_font"]
                assert len(font_issues) == 0, f"{name}: unexpected font error"


class TestPreflightFontParsing:
    """Unit tests for font declaration parsing."""

    def test_parse_single_font(self):
        from formforge.readiness import _parse_declared_fonts

        stacks = _parse_declared_fonts('#set text(font: "Inter")')
        assert stacks == [["Inter"]]

    def test_parse_font_stack(self):
        from formforge.readiness import _parse_declared_fonts

        stacks = _parse_declared_fonts('#set text(font: ("Inter", "Noto Sans"))')
        assert stacks == [["Inter", "Noto Sans"]]

    def test_parse_skips_jinja2_variable(self):
        from formforge.readiness import _parse_declared_fonts

        stacks = _parse_declared_fonts('#set text(font: "{{ custom_font }}")')
        assert stacks == []

    def test_parse_multiple_declarations(self):
        from formforge.readiness import _parse_declared_fonts

        source = '''
#set text(font: "Inter")
#show heading: set text(font: "Inter")
'''
        stacks = _parse_declared_fonts(source)
        assert len(stacks) == 2
        assert all(s == ["Inter"] for s in stacks)

    def test_parse_empty_source(self):
        from formforge.readiness import _parse_declared_fonts

        assert _parse_declared_fonts("") == []

    def test_enumerate_font_families(self):
        from formforge import bundled_font_dir
        from formforge.readiness import _enumerate_font_families

        fonts_dir = bundled_font_dir()
        if fonts_dir:
            families = _enumerate_font_families([str(fonts_dir)])
            assert "inter" in families


class TestPreflightRegression:
    def test_does_not_render(self):
        """preflight() should NOT produce a PDF — it's a dry run."""
        verdict = preflight(EXAMPLES / "invoice.j2.typ", _load_data("invoice"))
        # The verdict has no pdf_bytes attribute
        assert not hasattr(verdict, "pdf_bytes")
        assert isinstance(verdict.ready, bool)
