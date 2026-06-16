# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests de l'API FastAPI (fetch mocké)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from seryvon.api.main import app
from seryvon.core import audit as audit_module
from seryvon.crawler import extract_page_signals
from seryvon.crawler.discovery import DiscoveryResult, RobotsTxt
from seryvon.models.signals import PageSignals


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, sample_html: str) -> TestClient:
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
    return TestClient(app)


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_create_audit(client: TestClient) -> None:
    resp = client.post("/audits", json={"url": "https://example.com"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["domain"] == "example.com"
    assert "pillars" in data
    assert "seo" in data["pillars"]


def test_create_audit_rejects_bad_url(client: TestClient) -> None:
    resp = client.post("/audits", json={"url": "not-a-url"})
    assert resp.status_code == 422
