# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests de l'API FastAPI (fetch mocké)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from seryvon.api.main import app
from seryvon.core import audit as audit_module
from seryvon.crawler.fetch import FetchResult


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch, sample_html: str) -> TestClient:
    async def fake_fetch(url: str, **kwargs: object) -> FetchResult:
        return FetchResult(
            url=url,
            final_url="https://example.com/",
            status_code=200,
            html=sample_html,
            redirects=0,
        )

    monkeypatch.setattr(audit_module, "fetch_page", fake_fetch)
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
