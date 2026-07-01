# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Unit tests for Celery task helper functions (no broker required)."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from seryvon.core.config import Settings
from seryvon.models.prompts import PromptIntent

# ---------------------------------------------------------------------------
# citation.py helpers
# ---------------------------------------------------------------------------


def _settings(**api_keys: str) -> Settings:
    """Build a Settings instance with specific API key overrides (alias-aware)."""
    return Settings.model_validate(api_keys)


class TestBuildConnectors:
    def test_empty_when_no_keys(self) -> None:
        from seryvon.tasks.citation import _build_connectors

        s = _settings()
        assert _build_connectors(s) == []

    def test_perplexity_only(self) -> None:
        from seryvon.citation.perplexity import PerplexityConnector
        from seryvon.tasks.citation import _build_connectors

        s = _settings(PERPLEXITY_API_KEY="pplx-test")
        connectors = _build_connectors(s)
        assert len(connectors) == 1
        assert isinstance(connectors[0], PerplexityConnector)

    def test_all_four_keys(self) -> None:
        from seryvon.tasks.citation import _build_connectors

        s = _settings(
            PERPLEXITY_API_KEY="pplx-test",
            OPENAI_API_KEY="sk-test",
            ANTHROPIC_API_KEY="ant-test",
            GEMINI_API_KEY="gem-test",
        )
        connectors = _build_connectors(s)
        assert len(connectors) == 4

    def test_openai_only(self) -> None:
        from seryvon.citation.engines import OpenAiConnector
        from seryvon.tasks.citation import _build_connectors

        s = _settings(OPENAI_API_KEY="sk-test")
        connectors = _build_connectors(s)
        assert len(connectors) == 1
        assert isinstance(connectors[0], OpenAiConnector)


class TestMinimalPromptSet:
    def test_always_five_prompts(self) -> None:
        from seryvon.tasks.citation import _minimal_prompt_set

        ps = _minimal_prompt_set("example.com", None, [])
        assert len(ps.prompts) == 5

    def test_covers_required_intents(self) -> None:
        from seryvon.tasks.citation import _minimal_prompt_set

        ps = _minimal_prompt_set("example.com", "MyBrand", [])
        intents = {p.intent for p in ps.prompts}
        assert PromptIntent.DEFINITIONAL in intents
        assert PromptIntent.RECOMMENDATION in intents
        assert PromptIntent.EXPLANATORY in intents
        assert PromptIntent.COMPARATIVE in intents

    def test_domain_fallback_when_no_brand(self) -> None:
        from seryvon.tasks.citation import _minimal_prompt_set

        ps = _minimal_prompt_set("example.com", None, [])
        texts = " ".join(p.text for p in ps.prompts)
        assert "example.com" in texts

    def test_brand_used_when_provided(self) -> None:
        from seryvon.tasks.citation import _minimal_prompt_set

        ps = _minimal_prompt_set("example.com", "Acme", [])
        texts = " ".join(p.text for p in ps.prompts)
        assert "Acme" in texts

    def test_competitors_stored(self) -> None:
        from seryvon.tasks.citation import _minimal_prompt_set

        ps = _minimal_prompt_set("example.com", None, ["rival.com", "other.io"])
        assert ps.tracked_competitors == ["rival.com", "other.io"]

    def test_domain_field(self) -> None:
        from seryvon.tasks.citation import _minimal_prompt_set

        ps = _minimal_prompt_set("my.site", None, [])
        assert ps.domain == "my.site"

    def test_quality_scores_nonzero(self) -> None:
        from seryvon.tasks.citation import _minimal_prompt_set

        ps = _minimal_prompt_set("example.com", None, [])
        for p in ps.prompts:
            assert p.quality_score > 0


# ---------------------------------------------------------------------------
# audit task (mock the heavy dependencies)
# ---------------------------------------------------------------------------


def _make_fake_report() -> Any:
    """A minimal stand-in for AuditReport."""
    r = MagicMock()
    r.domain = "example.com"
    return r


@contextmanager  # type: ignore[arg-type]
def _fake_session_scope():  # type: ignore[override]
    yield MagicMock()


class TestRunAuditTask:
    """Tests for the Celery audit task body.

    `run_audit_task.__wrapped__` is already bound to the task instance, so
    `self` is not passed explicitly — `update_state` is patched on the task.
    """

    def test_returns_audit_id_and_logs(self) -> None:
        from seryvon.tasks.audit import run_audit_task

        fake_report = _make_fake_report()
        fake_audit_id = uuid.uuid4()

        with (
            patch("seryvon.tasks.audit.session_scope", _fake_session_scope),
            patch("seryvon.tasks.audit.resolve_settings", return_value=Settings()),
            patch(
                "seryvon.tasks.audit.run_audit",
                new=AsyncMock(return_value=(fake_report, [])),
            ),
            patch(
                "seryvon.tasks.audit.repository.persist_report",
                return_value=fake_audit_id,
            ),
            patch("seryvon.tasks.audit.repository.persist_pages"),
            patch.object(run_audit_task, "update_state"),
        ):
            result = run_audit_task.__wrapped__("https://example.com", locale="en")

        assert result["audit_id"] == str(fake_audit_id)
        assert "logs" in result

    def test_progress_callback_calls_update_state(self) -> None:
        """on_progress must trigger Celery update_state with PROGRESS."""
        from seryvon.tasks.audit import run_audit_task

        captured_on_progress: list[Any] = []

        async def _capture_run_audit(url: str, config: Any, **kwargs: Any) -> Any:
            on_prog = kwargs.get("on_progress")
            if on_prog:
                captured_on_progress.append(on_prog)
                on_prog("crawling depth=1")
            return (_make_fake_report(), [])

        with (
            patch("seryvon.tasks.audit.session_scope", _fake_session_scope),
            patch("seryvon.tasks.audit.resolve_settings", return_value=Settings()),
            patch("seryvon.tasks.audit.run_audit", new=_capture_run_audit),
            patch(
                "seryvon.tasks.audit.repository.persist_report",
                return_value=uuid.uuid4(),
            ),
            patch("seryvon.tasks.audit.repository.persist_pages"),
            patch.object(run_audit_task, "update_state") as mock_update,
        ):
            run_audit_task.__wrapped__("https://example.com")

        mock_update.assert_called()
        call_kwargs = mock_update.call_args
        assert call_kwargs.kwargs["state"] == "PROGRESS"
        assert "logs" in call_kwargs.kwargs["meta"]

    def test_locale_passed_to_config(self) -> None:
        from seryvon.tasks.audit import run_audit_task

        received_config: list[Any] = []

        async def _capture(url: str, config: Any, **kwargs: Any) -> Any:
            received_config.append(config)
            return (_make_fake_report(), [])

        with (
            patch("seryvon.tasks.audit.session_scope", _fake_session_scope),
            patch("seryvon.tasks.audit.resolve_settings", return_value=Settings()),
            patch("seryvon.tasks.audit.run_audit", new=_capture),
            patch(
                "seryvon.tasks.audit.repository.persist_report",
                return_value=uuid.uuid4(),
            ),
            patch("seryvon.tasks.audit.repository.persist_pages"),
            patch.object(run_audit_task, "update_state"),
        ):
            run_audit_task.__wrapped__("https://example.com", locale="fr")

        assert received_config[0].locale == "fr"


# ---------------------------------------------------------------------------
# citation task (mock the heavy dependencies)
# ---------------------------------------------------------------------------


class TestRunCitationTask:
    """Tests for the Celery citation task body (no broker required)."""

    def test_raises_when_no_connectors(self) -> None:
        from seryvon.tasks.citation import run_citation_task

        with (
            patch("seryvon.tasks.citation.session_scope", _fake_session_scope),
            patch("seryvon.tasks.citation.resolve_settings", return_value=_settings()),
            pytest.raises(ValueError, match="No LLM API keys"),
        ):
            run_citation_task.__wrapped__("example.com", None, [])

    def test_returns_metrics_dict(self) -> None:
        from seryvon.citation.aggregate import CitationMetrics
        from seryvon.tasks.citation import run_citation_task

        fake_metrics = MagicMock(spec=CitationMetrics)
        fake_metrics.model_dump.return_value = {"citation_rate": 0.5}

        with (
            patch("seryvon.tasks.citation.session_scope", _fake_session_scope),
            patch(
                "seryvon.tasks.citation.resolve_settings",
                return_value=_settings(PERPLEXITY_API_KEY="pplx-test"),
            ),
            patch(
                "seryvon.tasks.citation.run_tracking",
                new=AsyncMock(return_value=fake_metrics),
            ),
        ):
            result = run_citation_task.__wrapped__("example.com", None, [])

        assert result == {"citation_rate": 0.5}

    def test_raises_when_tracking_returns_none(self) -> None:
        from seryvon.tasks.citation import run_citation_task

        with (
            patch("seryvon.tasks.citation.session_scope", _fake_session_scope),
            patch(
                "seryvon.tasks.citation.resolve_settings",
                return_value=_settings(PERPLEXITY_API_KEY="pplx-test"),
            ),
            patch(
                "seryvon.tasks.citation.run_tracking",
                new=AsyncMock(return_value=None),
            ),
            pytest.raises(ValueError, match="No LLM responses"),
        ):
            run_citation_task.__wrapped__("example.com", None, [])
