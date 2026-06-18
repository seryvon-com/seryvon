# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests de la CLI (fetch mocké)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from seryvon.cli.main import app
from seryvon.core import audit as audit_module
from seryvon.crawler import extract_page_signals
from seryvon.crawler.discovery import DiscoveryResult, RobotsTxt
from seryvon.models.signals import PageSignals

runner = CliRunner()


@pytest.fixture(autouse=True)
def _patch_crawl(monkeypatch: pytest.MonkeyPatch, sample_html: str) -> None:
    async def fake_discover(url: str, **kwargs: object) -> DiscoveryResult:
        return DiscoveryResult(
            home_url="https://example.com/",
            origin="https://example.com",
            domain="example.com",
            robots=RobotsTxt.allow_all(),
            robots_found=False,
            crawl_delay=None,
            declared_sitemaps=[],
            sitemap_urls=[],
            sitemap_valid=False,
            home_allowed=True,
            frontier=["https://example.com/"],
        )

    async def fake_crawl(discovery: DiscoveryResult, **kwargs: object) -> list[PageSignals]:
        return [extract_page_signals("https://example.com/", sample_html, status_code=200)]

    monkeypatch.setattr(audit_module, "discover", fake_discover)
    monkeypatch.setattr(audit_module, "crawl_site", fake_crawl)


def test_version() -> None:
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "Seryvon" in result.stdout


def test_run_outputs_summary() -> None:
    result = runner.invoke(app, ["run", "https://example.com"])
    assert result.exit_code == 0
    assert "Score global" in result.stdout


def test_run_quiet_outputs_json() -> None:
    result = runner.invoke(app, ["run", "https://example.com", "--quiet"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["domain"] == "example.com"


def test_run_writes_output_file(tmp_path: Path) -> None:
    out = tmp_path / "report.json"
    result = runner.invoke(app, ["run", "https://example.com", "-o", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    data = json.loads(out.read_text())
    assert data["domain"] == "example.com"


def test_run_html_output(tmp_path: Path) -> None:
    out = tmp_path / "report.html"
    result = runner.invoke(app, ["run", "https://example.com", "-o", str(out), "-f", "html"])
    assert result.exit_code == 0
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "example.com" in content


def test_run_both_formats(tmp_path: Path) -> None:
    out = tmp_path / "report.json"
    result = runner.invoke(app, ["run", "https://example.com", "-o", str(out), "-f", "both"])
    assert result.exit_code == 0
    assert (tmp_path / "report.json").exists()
    assert (tmp_path / "report.html").exists()
    json.loads((tmp_path / "report.json").read_text(encoding="utf-8"))


def test_run_markdown_output(tmp_path: Path) -> None:
    out = tmp_path / "report.md"
    result = runner.invoke(app, ["run", "https://example.com", "-o", str(out), "-f", "md"])
    assert result.exit_code == 0
    content = out.read_text(encoding="utf-8")
    assert content.startswith("# Audit Seryvon")
    assert "Plan d'action" in content


def test_aso_command_not_yet_implemented() -> None:
    result = runner.invoke(app, ["aso", "https://example.com"])
    assert result.exit_code == 2
