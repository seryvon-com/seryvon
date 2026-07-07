# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the FastAPI API. /health without DB; audit endpoints gated (Postgres)."""

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


# --------------------------------------------------------------------------- #
# API-key middleware                                                           #
# --------------------------------------------------------------------------- #


def test_api_key_not_required_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """No SERYVON_API_KEY configured → all requests pass through."""
    monkeypatch.setattr("seryvon.core.config.get_settings.cache_clear", lambda: None)
    from seryvon.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("SERYVON_API_KEY", "")
    get_settings.cache_clear()
    resp = TestClient(app).get("/health")
    assert resp.status_code == 200


def test_api_key_enforced_when_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """SERYVON_API_KEY set → request without header returns 401."""
    from seryvon.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("SERYVON_API_KEY", "test-secret")
    get_settings.cache_clear()
    try:
        resp = TestClient(app).get("/audits")
        assert resp.status_code == 401
    finally:
        monkeypatch.delenv("SERYVON_API_KEY", raising=False)
        get_settings.cache_clear()


def test_api_key_accepted_with_correct_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """Correct X-API-Key header → request is forwarded (not 401)."""
    from seryvon.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("SERYVON_API_KEY", "test-secret")
    get_settings.cache_clear()
    try:
        resp = TestClient(app).get("/health", headers={"X-API-Key": "test-secret"})
        assert resp.status_code == 200
    finally:
        monkeypatch.delenv("SERYVON_API_KEY", raising=False)
        get_settings.cache_clear()


def test_health_exempt_from_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """/health is reachable without X-API-Key even when a key is configured."""
    from seryvon.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("SERYVON_API_KEY", "test-secret")
    get_settings.cache_clear()
    try:
        resp = TestClient(app).get("/health")
        assert resp.status_code == 200
    finally:
        monkeypatch.delenv("SERYVON_API_KEY", raising=False)
        get_settings.cache_clear()


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
        pytest.skip("SERYVON_TEST_DATABASE_URL not set (Postgres required)")
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


def test_compare_two_scorecards_exact(db_client: TestClient) -> None:
    """Two identical-profile audits compare as exact (M6)."""
    a = db_client.post("/audits", json={"url": "https://example.com"})
    b = db_client.post("/audits", json={"url": "https://example.com"})
    left = a.headers["location"].rsplit("/", 1)[-1]
    right = b.headers["location"].rsplit("/", 1)[-1]
    resp = db_client.post(
        "/scorecards/compare",
        json={"left_run_id": left, "right_run_id": right, "mode": "strict"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["comparability"] == "exact"
    assert body["global_delta"] == 0.0  # deterministic: same site, zero variance


def test_compare_unknown_run_returns_404(db_client: TestClient) -> None:
    resp = db_client.post(
        "/scorecards/compare",
        json={"left_run_id": str(uuid.uuid4()), "right_run_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


# --------------------------------------------------------------------------- #
# Rank tracking live re-fetch (no DB: session + collaborators are patched)     #
# --------------------------------------------------------------------------- #
@pytest.fixture
def rank_client() -> Iterator[TestClient]:
    def _override() -> Iterator[None]:
        yield None

    app.dependency_overrides[get_session] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_rank_tracking_rejects_bad_days(rank_client: TestClient) -> None:
    aid = uuid.uuid4()
    assert rank_client.get(f"/audits/{aid}/rank-tracking?days=0").status_code == 422
    assert rank_client.get(f"/audits/{aid}/rank-tracking?days=999").status_code == 422


def test_rank_tracking_unknown_audit_404(
    rank_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from seryvon.api import main as api_main

    monkeypatch.setattr(api_main.repository, "load_report", lambda _s, _a: None)
    resp = rank_client.get(f"/audits/{uuid.uuid4()}/rank-tracking?days=10")
    assert resp.status_code == 404


def test_rank_tracking_no_gsc_key_404(
    rank_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    from seryvon.api import main as api_main

    monkeypatch.setattr(
        api_main.repository, "load_report", lambda _s, _a: SimpleNamespace(domain="example.com")
    )
    monkeypatch.setattr(
        api_main, "resolve_settings", lambda _s: SimpleNamespace(gsc_service_account="")
    )
    resp = rank_client.get(f"/audits/{uuid.uuid4()}/rank-tracking?days=10")
    assert resp.status_code == 404


def test_rank_tracking_happy_path(
    rank_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace
    from typing import Any

    from seryvon.api import main as api_main
    from seryvon.models.signals import GscComparison, GscResult

    monkeypatch.setattr(
        api_main.repository, "load_report", lambda _s, _a: SimpleNamespace(domain="example.com")
    )
    monkeypatch.setattr(
        api_main, "resolve_settings", lambda _s: SimpleNamespace(gsc_service_account="{}")
    )

    async def fake_fetch(domain: str, **kwargs: Any) -> GscResult:
        assert domain == "example.com"
        assert kwargs["date_range_days"] == 10
        return GscResult(
            avg_position=12.4,
            date_range_days=kwargs["date_range_days"],
            comparison=GscComparison(period_days=kwargs["date_range_days"], position_delta=-1.5),
        )

    monkeypatch.setattr(api_main, "fetch_gsc", fake_fetch)
    resp = rank_client.get(f"/audits/{uuid.uuid4()}/rank-tracking?days=10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["date_range_days"] == 10
    assert body["avg_position"] == 12.4
    assert body["comparison"]["position_delta"] == -1.5
