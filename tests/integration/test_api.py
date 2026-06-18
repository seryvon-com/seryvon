# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests de l'API FastAPI. /health sans DB ; endpoints d'audit gated (Postgres)."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from seryvon.api.main import app, get_session
from seryvon.core import audit as audit_module
from seryvon.crawler import extract_page_signals
from seryvon.crawler.discovery import DiscoveryResult, RobotsTxt
from seryvon.db.base import Base
from seryvon.models.signals import PageSignals

_TEST_DB = os.environ.get("SERYVON_TEST_DATABASE_URL")


def test_health() -> None:
    resp = TestClient(app).get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.fixture
def _mock_crawl(monkeypatch: pytest.MonkeyPatch, sample_html: str) -> None:
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


@pytest.fixture
def db_client(_mock_crawl: None) -> Iterator[TestClient]:
    if not _TEST_DB:
        pytest.skip("SERYVON_TEST_DATABASE_URL non défini (Postgres requis)")
    engine = create_engine(_TEST_DB, future=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session: Session = sessionmaker(bind=engine, expire_on_commit=False)()

    def _override() -> Iterator[Session]:
        yield session

    app.dependency_overrides[get_session] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()
    session.close()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_create_audit_persists(db_client: TestClient) -> None:
    resp = db_client.post("/audits", json={"url": "https://example.com"})
    assert resp.status_code == 200
    assert resp.json()["domain"] == "example.com"
    assert resp.headers["location"].startswith("/audits/")


def test_create_then_get(db_client: TestClient) -> None:
    created = db_client.post("/audits", json={"url": "https://example.com"})
    audit_id = created.headers["location"].rsplit("/", 1)[-1]
    fetched = db_client.get(f"/audits/{audit_id}")
    assert fetched.status_code == 200
    assert fetched.json()["domain"] == "example.com"


def test_list_audits_history(db_client: TestClient) -> None:
    db_client.post("/audits", json={"url": "https://example.com"})
    db_client.post("/audits", json={"url": "https://example.com"})
    resp = db_client.get("/audits", params={"domain": "example.com"})
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_unknown_returns_404(db_client: TestClient) -> None:
    resp = db_client.get(f"/audits/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_create_audit_rejects_bad_url(db_client: TestClient) -> None:
    resp = db_client.post("/audits", json={"url": "not-a-url"})
    assert resp.status_code == 422
