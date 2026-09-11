# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""CLI tests (fetch mocked)."""

from __future__ import annotations

import json
import runpy
import sys
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

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
from seryvon.models.prompts import Prompt, PromptIntent, PromptSet, ThemeProfile
from seryvon.models.signals import PageSignals

runner = CliRunner()


def _prompt_set() -> PromptSet:
    return PromptSet(
        domain="example.com",
        theme_profile=ThemeProfile(domain="example.com", brand="Example"),
        prompts=[Prompt(text="What is Example?", intent=PromptIntent.DEFINITIONAL)],
        tracked_competitors=["other.com"],
    )


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


def test_cli_module_entrypoint(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["seryvon", "--help"])
    with pytest.raises(SystemExit):
        runpy.run_module("seryvon.cli.main", run_name="__main__")


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


def test_run_pdf_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "report.json"
    monkeypatch.setattr(cli_main, "report_to_pdf", lambda _report: b"%PDF-test")
    result = runner.invoke(app, ["run", "https://example.com", "-o", str(out), "-f", "pdf"])
    assert result.exit_code == 0
    assert (tmp_path / "report.pdf").read_bytes() == b"%PDF-test"


def test_run_reports_pipeline_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("crawl failed")

    monkeypatch.setattr(cli_main, "run_audit", fail)
    result = runner.invoke(app, ["run", "https://example.com"])
    assert result.exit_code == 1
    assert "Échec de l'audit" in result.stdout


def test_run_persist_calls_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    saved: dict[str, object] = {}

    def fake_persist(report: object, session: object) -> uuid.UUID:
        saved["called"] = True
        return uuid.uuid4()

    monkeypatch.setattr(cli_main, "session_scope", _fake_scope)
    monkeypatch.setattr(repository, "persist_report", fake_persist)
    monkeypatch.setattr(repository, "persist_pages", lambda audit_id, pages, session: None)
    result = runner.invoke(app, ["run", "https://example.com", "--persist", "-q"])
    assert result.exit_code == 0
    assert saved.get("called") is True


def test_run_persist_reports_id(monkeypatch: pytest.MonkeyPatch) -> None:
    audit_id = uuid.uuid4()
    monkeypatch.setattr(cli_main, "session_scope", _fake_scope)
    monkeypatch.setattr(repository, "persist_report", lambda *_: audit_id)
    monkeypatch.setattr(repository, "persist_pages", lambda *_: None)
    result = runner.invoke(app, ["run", "https://example.com", "--persist"])
    assert result.exit_code == 0
    assert str(audit_id) in result.stdout


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


def test_cli_citation_helpers_cover_configured_engines_and_payloads() -> None:
    settings = type(
        "SettingsStub",
        (),
        {
            "perplexity_api_key": "p",
            "openai_api_key": "",
            "anthropic_api_key": "a",
            "gemini_api_key": "",
        },
    )()
    assert cli_main._configured_engines(settings) == ["perplexity", "anthropic"]
    connectors = cli_main._build_connectors(settings)
    assert [connector.provider for connector in connectors] == ["perplexity", "anthropic"]
    prompt_set = _prompt_set()
    dry = cli_main._dry_run_payload(prompt_set, 2, ["perplexity"])
    assert dry["call_volume"] == 2
    assert dry["prompts"][0]["intent"] == "definitional"
    payload = cli_main._citation_payload(prompt_set, None, ["perplexity"])
    assert payload["citation_metrics"] is None
    all_settings = type(
        "AllSettingsStub",
        (),
        {
            "perplexity_api_key": "",
            "openai_api_key": "o",
            "anthropic_api_key": "",
            "gemini_api_key": "g",
        },
    )()
    assert [c.provider for c in cli_main._build_connectors(all_settings)] == ["openai", "gemini"]


def test_print_citations_summary_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    payload = cli_main._dry_run_payload(_prompt_set(), 2, ["perplexity"])
    cli_main._print_citations_summary(payload, dry_run=True)
    assert "Prompt set" in capsys.readouterr().out


def test_print_citations_summary_without_metrics(capsys: pytest.CaptureFixture[str]) -> None:
    cli_main._print_citations_summary({"citation_metrics": None}, dry_run=False)
    assert "non mesurée" in capsys.readouterr().out


def test_print_citations_summary_with_metrics(capsys: pytest.CaptureFixture[str]) -> None:
    cli_main._print_citations_summary(
        {
            "domain": "example.com",
            "citation_metrics": {
                "citation_rate": 0.5,
                "mention_rate": 0.75,
                "citation_confidence": 0.8,
                "per_engine": {"perplexity": {"citation_rate": 0.5, "mention_rate": 0.75}},
            },
        },
        dry_run=False,
    )
    output = capsys.readouterr().out
    assert "Citation LLM" in output
    assert "perplexity" in output


def test_write_report_pdf_import_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(
        cli_main,
        "report_to_pdf",
        lambda _: (_ for _ in ()).throw(ImportError("WeasyPrint missing")),
    )
    with pytest.raises(cli_main.typer.Exit):
        cli_main._write_report(
            object(), tmp_path / "report.json", cli_main.OutputFormat.pdf, quiet=True
        )


def test_print_aso_summary_includes_blocked_bots(capsys: pytest.CaptureFixture[str]) -> None:
    readiness = SimpleNamespace(
        readiness_level=SimpleNamespace(value="partial"),
        agent_ready=False,
        has_webmcp=False,
        has_action_schema=False,
        ai_discovery_endpoints=0,
        has_nlweb=False,
        brand_coherence_score=None,
        blocked_agent_bots=["GPTBot"],
    )
    pillar = SimpleNamespace(score=42.0, measured=1, excluded=0)
    cli_main._print_aso_summary(
        SimpleNamespace(
            domain="example.com", pillars={"aso": pillar}, aso_readiness=readiness, criteria=[]
        )
    )
    assert "GPTBot" in capsys.readouterr().out


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


def test_aso_reports_pipeline_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail(*_: object, **__: object) -> object:
        raise RuntimeError("aso failed")

    monkeypatch.setattr(cli_main, "run_audit", fail)
    result = runner.invoke(app, ["aso", "https://example.com"])
    assert result.exit_code == 1
    assert "Échec de l'audit" in result.stdout


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


def test_citations_reports_pipeline_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        cli_main,
        "get_settings",
        lambda: SimpleNamespace(
            perplexity_api_key="p", openai_api_key="", anthropic_api_key="", gemini_api_key=""
        ),
    )

    async def fail(*_: object, **__: object) -> object:
        raise RuntimeError("citation failed")

    monkeypatch.setattr(cli_main, "_run_citations", fail)
    result = runner.invoke(app, ["citations", "https://example.com"])
    assert result.exit_code == 1
    assert "Échec du suivi" in result.stdout


def test_citations_writes_report_and_prints_summary(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(
        cli_main,
        "get_settings",
        lambda: SimpleNamespace(
            perplexity_api_key="p", openai_api_key="", anthropic_api_key="", gemini_api_key=""
        ),
    )

    async def fake_run(*_: object, **__: object) -> dict[str, object]:
        return {"domain": "example.com", "citation_metrics": None}

    monkeypatch.setattr(cli_main, "_run_citations", fake_run)
    out = tmp_path / "citations.json"
    result = runner.invoke(app, ["citations", "https://example.com", "-o", str(out)])
    assert result.exit_code == 0
    assert out.exists()
    assert "Rapport citation écrit" in result.stdout


def test_compare_outputs_summary() -> None:
    """compare runs two audits and prints a comparison summary."""
    result = runner.invoke(app, ["compare", "https://example.com", "https://competitor.com"])
    assert result.exit_code == 0
    assert "Comparaison" in result.stdout
    assert "Par pilier" in result.stdout


def test_compare_invalid_mode() -> None:
    result = runner.invoke(
        app, ["compare", "https://example.com", "https://competitor.com", "--mode", "bogus"]
    )
    assert result.exit_code == 1
    assert "Mode invalide" in result.stdout


def test_compare_reports_first_audit_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fail(*args: object, **kwargs: object) -> object:
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(cli_main, "run_audit", fail)
    result = runner.invoke(app, ["compare", "https://example.com", "https://other.com"])
    assert result.exit_code == 1
    assert "Échec de l'audit 1" in result.stdout


def test_compare_reports_second_audit_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    async def fake_run(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("competitor unavailable")
        return object(), []

    monkeypatch.setattr(cli_main, "run_audit", fake_run)
    result = runner.invoke(app, ["compare", "https://example.com", "https://other.com"])
    assert result.exit_code == 1
    assert "Échec de l'audit 2" in result.stdout


def test_compare_reports_incomparable_profiles(monkeypatch: pytest.MonkeyPatch) -> None:
    from seryvon.scoring.comparison import Comparability, ComparisonMode, IncomparableError

    async def fake_run(*args: object, **kwargs: object) -> object:
        return object(), []

    def fail_compare(*args: object, **kwargs: object) -> object:
        raise IncomparableError(
            Comparability.INCOMPATIBLE,
            ComparisonMode.STRICT,
            ["pillar_weights"],
            [ComparisonMode.DESCRIPTIVE],
        )

    monkeypatch.setattr(cli_main, "run_audit", fake_run)
    monkeypatch.setattr("seryvon.scoring.comparison.compare_scorecards", fail_compare)
    result = runner.invoke(
        app,
        ["compare", "https://example.com", "https://other.com", "--mode", "strict"],
    )
    assert result.exit_code == 3
    assert "Comparaison impossible" in result.stdout


def test_print_comparison_renders_optional_sections(capsys: pytest.CaptureFixture[str]) -> None:
    result = SimpleNamespace(
        comparability=SimpleNamespace(value="intersection"),
        recomputed=True,
        common_criteria=["a", "b"],
        profile_differences=["thresholds"],
        left_global=None,
        right_global=80.0,
        global_delta=None,
        pillars=[
            SimpleNamespace(pillar="seo", left_score=None, right_score=80.0, delta=-2.0),
        ],
        criteria=[
            SimpleNamespace(key="a", left_score=40.0, right_score=80.0, delta=40.0),
        ],
    )
    cli_main._print_comparison("left.example", "right.example", result)
    output = capsys.readouterr().out
    assert "Scores recalculés" in output
    assert "Différences de profil" in output
    assert "Critères les plus impactés" in output


def test_recalc_scores_dry_run_reports_audits(monkeypatch: pytest.MonkeyPatch) -> None:
    audit_id = uuid.uuid4()
    criterion = SimpleNamespace(
        criterion_key="meta.title", pillars=["seo"], score=80.0, status="ok", weight=1.0
    )
    audit_row = SimpleNamespace(domain=SimpleNamespace(host="example.com"))

    class FakeSession:
        def scalars(self, statement: object) -> object:
            text = str(statement)
            if "criterion_result" in text:
                return SimpleNamespace(all=lambda: [criterion])
            return SimpleNamespace(all=lambda: [audit_id])

        def get(self, model: object, key: object) -> object:
            return audit_row

    @contextmanager
    def fake_scope() -> Iterator[FakeSession]:
        yield FakeSession()

    monkeypatch.setattr(cli_main, "session_scope", fake_scope)
    result = runner.invoke(app, ["recalc-scores", "--dry-run"])
    assert result.exit_code == 0
    assert "audit(s) trouvé(s)" in result.stdout
    assert "example.com" in result.stdout
    assert "à recalculer" in result.stdout


def test_recalc_scores_writes_scores_and_skips_empty_audits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit_id = uuid.uuid4()
    empty_id = uuid.uuid4()
    criterion = SimpleNamespace(
        criterion_key="meta.title", pillars=["seo"], score=80.0, status="ok", weight=1.0
    )
    pillar_rows = [
        SimpleNamespace(
            pillar=p,
            score=0.0,
            coverage=0.0,
            coverage_label="insufficient",
            measured=0,
            excluded=0,
            not_applicable=0,
        )
        for p in ("seo", "geo", "gso", "aeo", "aso")
    ]
    audit_row = SimpleNamespace(domain=SimpleNamespace(host="example.com"), score_global=0.0)
    criterion_calls = 0
    committed = False

    class FakeSession:
        def scalars(self, statement: object) -> object:
            nonlocal criterion_calls
            text = str(statement)
            if "audit.id" in text and "criterion_result" not in text:
                return SimpleNamespace(all=lambda: [audit_id, empty_id])
            if "criterion_result" in text:
                criterion_calls += 1
                return SimpleNamespace(all=lambda: [criterion] if criterion_calls == 1 else [])
            return SimpleNamespace(all=lambda: pillar_rows)

        def get(self, model: object, key: object) -> object:
            return audit_row

        def commit(self) -> None:
            nonlocal committed
            committed = True

    @contextmanager
    def fake_scope() -> Iterator[FakeSession]:
        yield FakeSession()

    monkeypatch.setattr(cli_main, "session_scope", fake_scope)
    result = runner.invoke(app, ["recalc-scores"])
    assert result.exit_code == 0
    assert committed is True
    assert audit_row.score_global != 0.0
    assert any(row.measured == 1 for row in pillar_rows if row.pillar == "seo")
    assert "1 audit(s) mis à jour, 1 ignoré(s)" in result.stdout


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
