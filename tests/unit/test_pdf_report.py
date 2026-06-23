# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Tests for PDF export (requires seryvon[pdf] / WeasyPrint)."""

from __future__ import annotations

import datetime
import uuid

import pytest

from seryvon.models.report import AuditReport

# Skip the whole module if WeasyPrint is not installed.
weasyprint = pytest.importorskip(
    "weasyprint", reason="WeasyPrint not installed (pip install 'seryvon[pdf]')"
)


def _minimal_report() -> AuditReport:
    return AuditReport(
        audit_id=uuid.uuid4(),
        domain="example.com",
        seed_url="https://example.com",
        score_global=72.5,
        coverage=0.85,
        pillars={},
        criteria=[],
        issues=[],
        active_connectors=[],
        started_at=datetime(2026, 6, 23, 12, 0, 0, tzinfo=datetime.UTC),
        finished_at=datetime(2026, 6, 23, 12, 0, 30, tzinfo=datetime.UTC),
    )


def test_report_to_pdf_returns_bytes() -> None:
    from seryvon.reporting.pdf_report import report_to_pdf

    pdf = report_to_pdf(_minimal_report())
    assert isinstance(pdf, bytes)
    assert len(pdf) > 1024  # non-trivial output


def test_report_to_pdf_starts_with_pdf_magic() -> None:
    from seryvon.reporting.pdf_report import report_to_pdf

    pdf = report_to_pdf(_minimal_report())
    assert pdf[:4] == b"%PDF"


def test_report_to_pdf_importerror_without_weasyprint(monkeypatch: pytest.MonkeyPatch) -> None:
    """Importing pdf_report raises ImportError with a helpful message when WeasyPrint is absent."""
    import builtins

    real_import = builtins.__import__

    def _block_weasyprint(name: str, *args: object, **kwargs: object) -> object:
        if name == "weasyprint":
            raise ModuleNotFoundError("No module named 'weasyprint'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", _block_weasyprint)

    import importlib

    from seryvon.reporting import pdf_report

    importlib.reload(pdf_report)

    with pytest.raises(ImportError, match="seryvon\\[pdf\\]"):
        pdf_report.report_to_pdf(_minimal_report())
