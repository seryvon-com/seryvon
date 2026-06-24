# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Unit tests for the audit cost estimator (pure, no I/O)."""

from __future__ import annotations

import pytest

from seryvon.core.audit_cost import (
    AuditCostEstimate,
    ConnectorLine,
    _DATAFORSEO_PER_CALL,
    _SERPAPI_PER_SEARCH,
    _SERPAPI_PROBES,
    estimate_audit_cost,
)
from seryvon.core.config import Settings


def _settings(**kwargs: object) -> Settings:
    """Build a Settings with only the fields we care about, ignoring DB URLs."""
    return Settings.model_validate(
        {
            "database_url": "postgresql+psycopg://x:x@localhost/x",
            "redis_url": "redis://localhost:6379/0",
            "celery_broker_url": "redis://localhost:6379/1",
            "celery_result_backend": "redis://localhost:6379/2",
            **kwargs,
        }
    )


# --------------------------------------------------------------------------- #
# No keys configured (free-only audit)                                        #
# --------------------------------------------------------------------------- #
def test_no_keys_zero_cost() -> None:
    est = estimate_audit_cost(_settings())
    assert est.total_usd == 0.0
    assert est.currency == "USD"
    assert est.indicative is True


def test_no_keys_free_connectors_inactive() -> None:
    est = estimate_audit_cost(_settings())
    by_name = {ln.connector: ln for ln in est.lines}
    assert not by_name["psi"].active
    assert not by_name["opr"].active
    assert not by_name["dataforseo"].active
    assert not by_name["serpapi"].active
    assert not by_name["gsc"].active


def test_wikidata_active_by_default() -> None:
    est = estimate_audit_cost(_settings())
    by_name = {ln.connector: ln for ln in est.lines}
    assert by_name["wikidata"].active
    assert by_name["wikidata"].total_usd == 0.0


# --------------------------------------------------------------------------- #
# DataForSEO active                                                            #
# --------------------------------------------------------------------------- #
def test_dataforseo_cost() -> None:
    est = estimate_audit_cost(_settings(DATAFORSEO_API_KEY="login:pass"))
    by_name = {ln.connector: ln for ln in est.lines}
    dfs = by_name["dataforseo"]
    assert dfs.active
    assert dfs.calls == 2
    assert dfs.total_usd == round(2 * _DATAFORSEO_PER_CALL, 4)
    assert est.total_usd == dfs.total_usd


# --------------------------------------------------------------------------- #
# SerpAPI active                                                               #
# --------------------------------------------------------------------------- #
def test_serpapi_cost() -> None:
    est = estimate_audit_cost(_settings(SERP_API_KEY="serpkey"))
    by_name = {ln.connector: ln for ln in est.lines}
    serp = by_name["serpapi"]
    assert serp.active
    assert serp.calls == _SERPAPI_PROBES
    expected = round(_SERPAPI_PROBES * _SERPAPI_PER_SEARCH, 4)
    assert serp.total_usd == expected
    assert est.total_usd == expected


# --------------------------------------------------------------------------- #
# All paid connectors active                                                   #
# --------------------------------------------------------------------------- #
def test_all_paid_connectors_total() -> None:
    est = estimate_audit_cost(
        _settings(
            DATAFORSEO_API_KEY="login:pass",
            SERP_API_KEY="serpkey",
        )
    )
    expected = round(2 * _DATAFORSEO_PER_CALL + _SERPAPI_PROBES * _SERPAPI_PER_SEARCH, 4)
    assert est.total_usd == expected


# --------------------------------------------------------------------------- #
# LLM citation informational line                                              #
# --------------------------------------------------------------------------- #
def test_llm_citation_line_present() -> None:
    est = estimate_audit_cost(_settings())
    by_name = {ln.connector: ln for ln in est.lines}
    llm = by_name["llm_citation"]
    assert llm.total_usd == 0.0
    assert llm.calls == 0


def test_llm_citation_reports_active_engines() -> None:
    est = estimate_audit_cost(_settings(OPENAI_API_KEY="sk-test", PERPLEXITY_API_KEY="px-test"))
    by_name = {ln.connector: ln for ln in est.lines}
    llm = by_name["llm_citation"]
    assert "openai" in llm.note
    assert "perplexity" in llm.note
    assert llm.total_usd == 0.0  # still not charged in audit cost


# --------------------------------------------------------------------------- #
# as_dict serialisation                                                        #
# --------------------------------------------------------------------------- #
def test_as_dict_keys() -> None:
    d = estimate_audit_cost(_settings()).as_dict()
    assert set(d.keys()) == {"currency", "total_usd", "indicative", "lines"}
    assert isinstance(d["lines"], list)
    line = d["lines"][0]
    assert set(line.keys()) == {"connector", "active", "calls", "unit_usd", "total_usd", "note"}
