# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Test d'intégration du flux d'audit (fetch mocké, pas de réseau réel)."""

from __future__ import annotations

import httpx
import pytest

from seryvon.core import audit as audit_module
from seryvon.core.audit import run_audit
from seryvon.crawler.fetch import FetchResult


@pytest.fixture
def patched_fetch(monkeypatch: pytest.MonkeyPatch, sample_html: str) -> None:
    async def fake_fetch(url: str, **kwargs: object) -> FetchResult:
        return FetchResult(
            url=url,
            final_url="https://example.com/",
            status_code=200,
            html=sample_html,
            redirects=0,
        )

    monkeypatch.setattr(audit_module, "fetch_page", fake_fetch)


async def test_full_audit_produces_report(patched_fetch: None) -> None:
    report = await run_audit("https://example.com")
    assert report.domain == "example.com"
    assert report.tool_version
    assert "seo" in report.pillars
    assert report.pillars["seo"].score > 0  # title présent dans le HTML d'exemple


async def test_audit_is_deterministic(patched_fetch: None) -> None:
    """Deux audits du même site -> mêmes scores (variance nulle)."""
    a = await run_audit("https://example.com")
    b = await run_audit("https://example.com")
    assert a.score_global == b.score_global
    assert a.config_digest == b.config_digest
    assert {p: s.score for p, s in a.pillars.items()} == {p: s.score for p, s in b.pillars.items()}


async def test_audit_network_error_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(url: str, **kwargs: object) -> FetchResult:
        raise httpx.ConnectError("unreachable")

    monkeypatch.setattr(audit_module, "fetch_page", boom)
    with pytest.raises(httpx.HTTPError):
        await run_audit("https://unreachable.example")
