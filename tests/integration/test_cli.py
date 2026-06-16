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
from seryvon.crawler.fetch import FetchResult

runner = CliRunner()


@pytest.fixture(autouse=True)
def _patch_fetch(monkeypatch: pytest.MonkeyPatch, sample_html: str) -> None:
    async def fake_fetch(url: str, **kwargs: object) -> FetchResult:
        return FetchResult(
            url=url,
            final_url="https://example.com/",
            status_code=200,
            html=sample_html,
            redirects=0,
        )

    monkeypatch.setattr(audit_module, "fetch_page", fake_fetch)


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


def test_aso_command_not_yet_implemented() -> None:
    result = runner.invoke(app, ["aso", "https://example.com"])
    assert result.exit_code == 2
