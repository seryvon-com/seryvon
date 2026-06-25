# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""CLI tests (fetch mocked)."""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from typer.testing import CliRunner

from seryvon.cli import main as cli_main
from seryvon.cli.main import app
from seryvon.core import audit as audit_module
from seryvon.crawler import extract_page_signals
from seryvon.crawler.discovery import DiscoveryResult, RobotsTxt
from seryvon.db import repository
from seryvon.db.repository import AuditSummary
from seryvon.models.llm import LlmCitation, LlmResponse
from seryvon.models.signals import PageSignals

runner = CliRunner()


@contextmanager
def _fake_scope() -> Iterator[object]:
    yield object()


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
    # The `citations` command uses discover/crawl_site bound in the CLI module.
    monkeypatch.setattr(cli_main, "discover", fake_discover, raising=False)
    monkeypatch.setattr(cli_main, "crawl_site", fake_crawl, raising=False)


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


def test_run_persist_calls_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    saved: dict[str, object] = {}

    def fake_persist(report: object, session: object) -> uuid.UUID:
        saved["called"] = True
        return uuid.uuid4()

    monkeypatch.setattr(cli_main, "session_scope", _fake_scope)
    monkeypatch.setattr(repository, "persist_report", fake_persist)
    result = runner.invoke(app, ["run", "https://example.com", "--persist", "-q"])
    assert result.exit_code == 0
    assert saved.get("called") is True


def test_history_renders_summaries(monkeypatch: pytest.MonkeyPatch) -> None:
    summaries = [
        AuditSummary(
            audit_id=uuid.uuid4(),
            domain="example.com",
            score_global=72.0,
            started_at=datetime(2026, 6, 18, 9, 0, tzinfo=UTC),
        )
    ]
    monkeypatch.setattr(cli_main, "session_scope", _fake_scope)
    monkeypatch.setattr(repository, "list_audits", lambda session, host: summaries)
    result = runner.invoke(app, ["history", "example.com"])
    assert result.exit_code == 0
    assert "Historique" in result.stdout


def test_history_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_main, "session_scope", _fake_scope)
    monkeypatch.setattr(repository, "list_audits", lambda session, host: [])
    result = runner.invoke(app, ["history", "example.com"])
    assert result.exit_code == 0
    assert "Aucun audit" in result.stdout


def test_aso_outputs_readiness() -> None:
    result = runner.invoke(app, ["aso", "https://example.com"])
    assert result.exit_code == 0
    assert "ASO" in result.stdout
    assert "Score ASO" in result.stdout


def test_aso_quiet_outputs_json() -> None:
    result = runner.invoke(app, ["aso", "https://example.com", "--quiet"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["domain"] == "example.com"
    assert payload["aso"]["pillar"] == "aso"
    assert "aso_readiness" in payload
    assert payload["criteria"], "at least one ASO criterion expected"
    assert all("aso" in c["pillars"] for c in payload["criteria"])


def test_aso_writes_output_file(tmp_path: Path) -> None:
    out = tmp_path / "aso.json"
    result = runner.invoke(app, ["aso", "https://example.com", "-o", str(out)])
    assert result.exit_code == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["aso"]["pillar"] == "aso"


class _NoKeySettings:
    perplexity_api_key = ""
    openai_api_key = ""
    anthropic_api_key = ""
    gemini_api_key = ""
    user_agent = "Seryvon/test"
    request_timeout = 5.0


def test_citations_dry_run_outputs_volume() -> None:
    result = runner.invoke(app, ["citations", "https://example.com", "--dry-run", "-q", "-k", "3"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is True
    assert payload["prompts"], "prompt set should not be empty"
    assert payload["call_volume"] == payload["prompt_count"] * 3 * 1
    assert payload["cost_estimate"]["indicative"] is True
    assert payload["cost_estimate"]["total"] >= 0.0


def test_citations_requires_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli_main, "get_settings", lambda: _NoKeySettings())
    result = runner.invoke(app, ["citations", "https://example.com"])
    assert result.exit_code == 2
    assert "LLM" in result.stdout


def test_compare_outputs_summary() -> None:
    """compare runs two audits and prints a comparison summary."""
    result = runner.invoke(
        app, ["compare", "https://example.com", "https://competitor.com"]
    )
    assert result.exit_code == 0
    assert "Comparaison" in result.stdout
    assert "Par pilier" in result.stdout


def test_compare_invalid_mode() -> None:
    result = runner.invoke(
        app, ["compare", "https://example.com", "https://competitor.com", "--mode", "bogus"]
    )
    assert result.exit_code == 1
    assert "Mode invalide" in result.stdout


def test_compare_writes_json_output(tmp_path: Path) -> None:
    out = tmp_path / "compare.json"
    result = runner.invoke(
        app,
        ["compare", "https://example.com", "https://competitor.com", "-o", str(out)],
    )
    assert result.exit_code == 0
    assert out.exists()
    data = json.loads(out.read_text())
    assert "comparability" in data
    assert "global_delta" in data


def test_citations_real_run_with_fake_connector(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Settings:
        perplexity_api_key = "pk"
        openai_api_key = ""
        anthropic_api_key = ""
        gemini_api_key = ""
        user_agent = "Seryvon/test"
        request_timeout = 5.0

    class _FakeConnector:
        provider = "perplexity"

        def __init__(self, *args: object, **kwargs: object) -> None: ...

        async def query(
            self, prompt: str, *, prompt_id: str = "", repetition: int = 1, **kwargs: object
        ) -> LlmResponse:
            return LlmResponse(
                engine="perplexity",
                model="sonar",
                prompt_id=prompt_id,
                repetition=repetition,
                response_text="cité",
                citations=[LlmCitation(url="https://example.com/", position=1)],
                web_search_enabled=True,
            )

    monkeypatch.setattr(cli_main, "get_settings", lambda: _Settings())
    monkeypatch.setattr(cli_main, "PerplexityConnector", _FakeConnector)
    result = runner.invoke(app, ["citations", "https://example.com", "-q", "-k", "2"])
    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["dry_run"] is False
    assert payload["citation_metrics"] is not None
    assert payload["citation_metrics"]["citation_rate"] == 1.0
