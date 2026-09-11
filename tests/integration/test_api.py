# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the FastAPI API. /health without DB; audit endpoints gated (Postgres)."""

from __future__ import annotations

import os
import uuid
from collections.abc import Iterator
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from seryvon.api import main as api_main
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


def test_list_keys_returns_one_status_per_connector(monkeypatch: pytest.MonkeyPatch) -> None:
    sentinel = api_main.KeyOut(
        connector="x", masked_value=None, source="none", created_at=None, updated_at=None
    )
    monkeypatch.setattr(
        api_main,
        "_connector_key_out",
        lambda connector, _session: sentinel.model_copy(update={"connector": connector}),
    )
    assert len(api_main.list_keys(None)) == len(  # type: ignore[arg-type]
        api_main.repository.CONNECTOR_FIELD
    )


def test_audit_cost_estimate_delegates_to_resolved_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    expected = {"currency": "USD", "total_usd": 0.0, "indicative": True, "lines": []}
    monkeypatch.setattr(
        "seryvon.core.settings_resolver.resolve_settings",
        lambda _session: SimpleNamespace(),
    )
    monkeypatch.setattr(
        "seryvon.core.audit_cost.estimate_audit_cost",
        lambda _settings: SimpleNamespace(as_dict=lambda: expected),
    )
    assert api_main.audit_cost_estimate(None) == expected  # type: ignore[arg-type]


def test_create_citation_tracking_dispatches_task(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import Response

    captured: dict[str, object] = {}

    def delay(domain: str, brand: str | None, competitors: list[str]) -> SimpleNamespace:
        captured.update(domain=domain, brand=brand, competitors=competitors)
        return SimpleNamespace(id="citation-task")

    monkeypatch.setattr(api_main.run_citation_task, "delay", delay)
    response = Response()
    result = api_main.create_citation_tracking(
        api_main.CitationRequest(domain="example.com", brand="Example", competitors=["rival"]),
        response,
    )
    assert result.task_id == "citation-task"
    assert response.headers["location"] == "/citations/tasks/citation-task"
    assert captured["domain"] == "example.com"


def test_encryption_guard_requires_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "get_settings", lambda: SimpleNamespace(secret_key=""))
    with pytest.raises(api_main.HTTPException) as exc:
        api_main._encryption_guard()
    assert exc.value.status_code == 503


def test_encryption_guard_returns_configured_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "get_settings", lambda: SimpleNamespace(secret_key="configured"))
    assert api_main._encryption_guard() == "configured"


def test_connector_key_out_uses_environment_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        api_main,
        "get_settings",
        lambda: SimpleNamespace(secret_key="", openai_api_key="env-secret"),
    )
    monkeypatch.setattr(api_main.repository, "get_key_row", lambda *_args: None)
    result = api_main._connector_key_out("openai", None)  # type: ignore[arg-type]
    assert result.source == "env"
    assert result.masked_value != "env-secret"


def test_connector_key_out_without_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        api_main, "get_settings", lambda: SimpleNamespace(secret_key="", openai_api_key="")
    )
    monkeypatch.setattr(api_main.repository, "get_key_row", lambda *_args: None)
    result = api_main._connector_key_out("openai", None)  # type: ignore[arg-type]
    assert result.source == "none"
    assert result.masked_value is None


def test_connector_key_out_decrypts_database_value(monkeypatch: pytest.MonkeyPatch) -> None:
    from cryptography.fernet import Fernet

    from seryvon.core.crypto import encrypt_value

    secret = Fernet.generate_key().decode()
    row = SimpleNamespace(
        encrypted_value=encrypt_value(secret, "openai-live-token"),
        created_at=None,
        updated_at=None,
    )
    monkeypatch.setattr(
        api_main, "get_settings", lambda: SimpleNamespace(secret_key=secret, openai_api_key="")
    )
    monkeypatch.setattr(api_main.repository, "get_key_row", lambda *_args: row)
    result = api_main._connector_key_out("openai", None)  # type: ignore[arg-type]
    assert result.source == "db"
    assert result.masked_value == "open...oken"


def test_connector_key_out_masks_corrupt_database_value(monkeypatch: pytest.MonkeyPatch) -> None:
    row = SimpleNamespace(encrypted_value=b"corrupt", created_at=None, updated_at=None)
    monkeypatch.setattr(
        api_main,
        "get_settings",
        lambda: SimpleNamespace(secret_key="test-secret-key", openai_api_key=""),
    )
    monkeypatch.setattr(api_main.repository, "get_key_row", lambda *_args: row)
    result = api_main._connector_key_out("openai", None)  # type: ignore[arg-type]
    assert result.source == "db"
    assert result.masked_value == "***"


@pytest.mark.asyncio
async def test_upsert_key_rejects_unknown_and_empty_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with pytest.raises(api_main.HTTPException) as unknown:
        await api_main.upsert_key("unknown", api_main.KeyIn(value="x"), None)  # type: ignore[arg-type]
    assert unknown.value.status_code == 404

    monkeypatch.setattr(api_main, "_encryption_guard", lambda: "secret")
    with pytest.raises(api_main.HTTPException) as empty:
        await api_main.upsert_key("openai", api_main.KeyIn(value="  "), None)  # type: ignore[arg-type]
    assert empty.value.status_code == 422


@pytest.mark.asyncio
async def test_upsert_key_encrypts_and_returns_masked_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from cryptography.fernet import Fernet

    stored: dict[str, object] = {}
    secret = Fernet.generate_key().decode()
    monkeypatch.setattr(api_main, "_encryption_guard", lambda: secret)
    monkeypatch.setattr(api_main, "_validate_key", lambda *_args: __import__("asyncio").sleep(0))
    monkeypatch.setattr(
        api_main.repository,
        "upsert_key",
        lambda _session, connector, encrypted: stored.update(
            connector=connector, encrypted=encrypted
        ),
    )
    monkeypatch.setattr(
        api_main,
        "_connector_key_out",
        lambda connector, _session: api_main.KeyOut(
            connector=connector,
            masked_value="abc...xyz",
            source="db",
            created_at=None,
            updated_at=None,
        ),
    )
    result = await api_main.upsert_key("openai", api_main.KeyIn(value=" token "), None)  # type: ignore[arg-type]
    assert result.source == "db"
    assert stored["connector"] == "openai"
    assert stored["encrypted"] != b"token"


def test_delete_key_rejects_unknown_connector() -> None:
    with pytest.raises(api_main.HTTPException) as exc:
        api_main.delete_key("unknown", None)  # type: ignore[arg-type]
    assert exc.value.status_code == 404


def test_delete_key_reports_missing_stored_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api_main, "_encryption_guard", lambda: "secret")
    monkeypatch.setattr(api_main.repository, "delete_key", lambda *_args: False)
    with pytest.raises(api_main.HTTPException) as exc:
        api_main.delete_key("openai", None)  # type: ignore[arg-type]
    assert exc.value.status_code == 404


def test_get_audit_and_prompt_set_handle_missing_reports(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit_id = uuid.uuid4()
    monkeypatch.setattr(api_main.repository, "load_report", lambda _session, _id: None)
    with pytest.raises(api_main.HTTPException) as audit_exc:
        api_main.get_audit(audit_id, None)  # type: ignore[arg-type]
    with pytest.raises(api_main.HTTPException) as prompt_exc:
        api_main.get_prompt_set(audit_id, None)  # type: ignore[arg-type]
    assert audit_exc.value.status_code == prompt_exc.value.status_code == 404


def test_get_audit_returns_persisted_report(monkeypatch: pytest.MonkeyPatch) -> None:
    from seryvon.models.report import AuditReport

    report = AuditReport(
        domain="example.com",
        tool_version="test",
        schema_version=1,
        started_at="2026-01-01T00:00:00Z",  # type: ignore[arg-type]
    )
    monkeypatch.setattr(api_main.repository, "load_report", lambda _session, _id: report)
    assert api_main.get_audit(uuid.uuid4(), None) is report  # type: ignore[arg-type]


def test_get_prompt_set_returns_persisted_value(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    prompt = SimpleNamespace(domain="example.com")
    monkeypatch.setattr(
        api_main.repository,
        "load_report",
        lambda _session, _id: SimpleNamespace(prompt_set=prompt),
    )
    assert api_main.get_prompt_set(uuid.uuid4(), None) is prompt  # type: ignore[arg-type]


def test_get_prompt_set_rejects_report_without_prompt_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        api_main.repository,
        "load_report",
        lambda _session, _id: SimpleNamespace(prompt_set=None),
    )
    with pytest.raises(api_main.HTTPException) as exc:
        api_main.get_prompt_set(uuid.uuid4(), None)  # type: ignore[arg-type]
    assert exc.value.status_code == 404


def test_get_audit_pages_maps_signal_counters() -> None:
    page = SimpleNamespace(
        url="https://example.com/",
        status_code=200,
        render_mode="ssr",
    )
    signal = SimpleNamespace(
        internal={
            "word_count": 120,
            "raw_word_count": 100,
            "rendered_word_count": 120,
            "title": "Example",
            "images_total": 4,
            "images_with_alt": 3,
            "svg_total": 2,
            "svg_accessible": 1,
            "aso": {"agent_usable_forms": 2, "agent_usable_forms_detail": {"found": 3}},
        }
    )

    class SessionStub:
        def execute(self, _query: object) -> SimpleNamespace:
            return SimpleNamespace(all=lambda: [(page, signal)])

    rows = api_main.get_audit_pages(uuid.uuid4(), SessionStub())  # type: ignore[arg-type]
    assert rows[0].images_missing_alt == 1
    assert rows[0].svg_missing_name == 1
    assert rows[0].forms_total == 3
    assert rows[0].agent_usable_forms == 2


def test_get_audit_pages_handles_page_without_signal_row() -> None:
    page = SimpleNamespace(url="https://example.com/empty", status_code=404, render_mode=None)

    class SessionStub:
        def execute(self, _query: object) -> SimpleNamespace:
            return SimpleNamespace(all=lambda: [(page, None)])

    row = api_main.get_audit_pages(uuid.uuid4(), SessionStub())  # type: ignore[arg-type]
    assert row[0].url.endswith("empty")
    assert row[0].images_missing_alt is None
    assert row[0].forms_total is None


@pytest.mark.parametrize("existing", [True, False])
def test_get_audit_pages_empty_result_checks_audit_existence(existing: bool) -> None:
    class SessionStub:
        def execute(self, _query: object) -> SimpleNamespace:
            return SimpleNamespace(all=lambda: [])

        def get(self, _model: object, _audit_id: object) -> object:
            return object() if existing else None

    audit_id = uuid.uuid4()
    if existing:
        assert api_main.get_audit_pages(audit_id, SessionStub()) == []  # type: ignore[arg-type]
    else:
        with pytest.raises(api_main.HTTPException) as exc:
            api_main.get_audit_pages(audit_id, SessionStub())  # type: ignore[arg-type]
        assert exc.value.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("connector", "status"),
    [
        ("dataforseo", 200),
        ("psi", 400),
        ("opr", 200),
        ("openai", 200),
        ("anthropic", 429),
        ("gemini", 200),
        ("perplexity", 404),
        ("serp", 429),
    ],
)
async def test_validate_key_accepts_provider_probe_statuses(
    monkeypatch: pytest.MonkeyPatch, connector: str, status: int
) -> None:
    import httpx

    class FakeClient:
        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def get(self, *_args: object, **_kwargs: object) -> httpx.Response:
            return httpx.Response(status, request=httpx.Request("GET", "https://example.com"))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: FakeClient())
    value = "login:password" if connector == "dataforseo" else "key"
    await api_main._validate_key(connector, value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("connector", "status"),
    [
        ("dataforseo", 401),
        ("psi", 403),
        ("opr", 401),
        ("openai", 401),
        ("anthropic", 401),
        ("gemini", 400),
        ("perplexity", 401),
        ("serp", 401),
    ],
)
async def test_validate_key_rejects_provider_auth_failures(
    monkeypatch: pytest.MonkeyPatch, connector: str, status: int
) -> None:
    import httpx

    class FakeClient:
        async def __aenter__(self) -> FakeClient:
            return self

        async def __aexit__(self, *_: object) -> None:
            return None

        async def get(self, *_args: object, **_kwargs: object) -> httpx.Response:
            return httpx.Response(status, request=httpx.Request("GET", "https://example.com"))

    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: FakeClient())
    value = "login:password" if connector == "dataforseo" else "key"
    with pytest.raises(api_main.HTTPException, match=r"invalid|rejected|authentication"):
        await api_main._validate_key(connector, value)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "connector",
    ["dataforseo", "psi", "opr", "openai", "anthropic", "gemini", "perplexity", "serp"],
)
async def test_validate_key_tolerates_network_failures(
    monkeypatch: pytest.MonkeyPatch, connector: str
) -> None:
    import httpx

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline")

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: client)
    value = "login:password" if connector == "dataforseo" else "key"
    await api_main._validate_key(connector, value)
    await client.aclose()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "connector",
    ["dataforseo", "psi", "opr", "openai", "anthropic", "gemini", "perplexity", "serp"],
)
async def test_validate_key_rejects_unexpected_provider_status(
    monkeypatch: pytest.MonkeyPatch, connector: str
) -> None:
    import httpx

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda _request: httpx.Response(
                500, request=httpx.Request("GET", "https://example.com")
            )
        )
    )
    monkeypatch.setattr(httpx, "AsyncClient", lambda **_kwargs: client)
    value = "login:password" if connector == "dataforseo" else "key"
    with pytest.raises(api_main.HTTPException, match="unexpected response"):
        await api_main._validate_key(connector, value)
    await client.aclose()


@pytest.mark.asyncio
async def test_validate_key_rejects_malformed_dataforseo_key() -> None:
    with pytest.raises(api_main.HTTPException, match="login:password"):
        await api_main._validate_key("dataforseo", "malformed")


@pytest.mark.asyncio
async def test_validate_key_rejects_invalid_gsc_payloads() -> None:
    with pytest.raises(api_main.HTTPException, match="valid service account JSON"):
        await api_main._validate_key("gsc", "not-json")
    with pytest.raises(api_main.HTTPException, match="missing required fields"):
        await api_main._validate_key("gsc", '{"type":"service_account"}')
    with pytest.raises(api_main.HTTPException, match=r"type.*service_account"):
        await api_main._validate_key("gsc", '{"type":"user","client_email":"a","private_key":"b"}')


@pytest.mark.parametrize(
    ("state", "expected"),
    [("PENDING", "pending"), ("STARTED", "running"), ("PROGRESS", "running")],
)
def test_audit_task_status_maps_non_terminal_states(
    monkeypatch: pytest.MonkeyPatch, state: str, expected: str
) -> None:
    monkeypatch.setattr(
        api_main,
        "AsyncResult",
        lambda *_args, **_kwargs: SimpleNamespace(state=state, info={"logs": ["progress"]}),
    )
    result = api_main._audit_task_status("task")
    assert result.status == expected


def test_audit_task_status_maps_success_and_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    result = SimpleNamespace(state="SUCCESS", result={"audit_id": "a1", "logs": ["done"]})
    monkeypatch.setattr(api_main, "AsyncResult", lambda *_args, **_kwargs: result)
    success = api_main._audit_task_status("task")
    assert success.status == "done"
    assert success.audit_id == "a1"
    assert success.logs == ["done"]

    result.state = "FAILURE"
    result.result = RuntimeError("failed")
    failure = api_main._audit_task_status("task")
    assert failure.status == "failed"
    assert failure.error == "failed"


def test_citation_task_status_maps_all_states(monkeypatch: pytest.MonkeyPatch) -> None:
    result = SimpleNamespace(state="SUCCESS", result={"citation_rate": 0.5})
    monkeypatch.setattr(api_main, "AsyncResult", lambda *_args, **_kwargs: result)
    assert api_main._citation_task_status("task").metrics == {"citation_rate": 0.5}
    result.state = "FAILURE"
    result.result = RuntimeError("failed")
    assert api_main._citation_task_status("task").status == "failed"
    result.state = "STARTED"
    assert api_main._citation_task_status("task").status == "running"
    result.state = "PENDING"
    assert api_main._citation_task_status("task").status == "pending"


def test_get_citation_task_delegates_to_status_mapper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = api_main.CitationTaskStatus(status="running")
    monkeypatch.setattr(api_main, "_citation_task_status", lambda _task_id: expected)
    assert api_main.get_citation_task("task-id") is expected


def test_pdf_endpoint_passes_requested_locale(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PDF export forwards the UI locale without requiring a database service."""
    from types import SimpleNamespace

    from seryvon.api import main as api_main

    audit_id = uuid.uuid4()
    report = SimpleNamespace(domain="example.com")
    monkeypatch.setattr(api_main.repository, "load_report", lambda _s, _id: report)
    captured: dict[str, str] = {}

    def fake_set_locale(locale: str) -> str:
        captured["locale"] = locale
        return locale

    monkeypatch.setattr("seryvon.i18n.set_locale", fake_set_locale)
    monkeypatch.setattr("seryvon.reporting.pdf_report.report_to_pdf", lambda _r: b"%PDF-test")

    def override() -> Iterator[None]:
        yield None

    app.dependency_overrides[get_session] = override
    try:
        response = TestClient(app).get(f"/audits/{audit_id}/report.pdf?locale=en")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    assert response.content == b"%PDF-test"
    assert captured["locale"] == "en"


def test_pdf_endpoint_rejects_unknown_locale() -> None:
    response = TestClient(app).get(f"/audits/{uuid.uuid4()}/report.pdf?locale=de")
    assert response.status_code == 422


def test_pdf_endpoint_returns_404_for_unknown_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from seryvon.api import main as api_main

    monkeypatch.setattr(api_main.repository, "load_report", lambda _s, _id: None)

    def override() -> Iterator[None]:
        yield None

    app.dependency_overrides[get_session] = override
    try:
        response = TestClient(app).get(f"/audits/{uuid.uuid4()}/report.pdf")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 404


def test_pdf_endpoint_returns_501_when_pdf_dependency_is_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    from seryvon.api import main as api_main

    monkeypatch.setattr(
        api_main.repository,
        "load_report",
        lambda _s, _id: SimpleNamespace(domain="example.com"),
    )
    monkeypatch.setattr(
        "seryvon.reporting.pdf_report.report_to_pdf",
        lambda _r: (_ for _ in ()).throw(ImportError("WeasyPrint missing")),
    )

    def override() -> Iterator[None]:
        yield None

    app.dependency_overrides[get_session] = override
    try:
        response = TestClient(app).get(f"/audits/{uuid.uuid4()}/report.pdf")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 501
    assert "PDF export not available" in response.json()["detail"]


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
def db_client(_mock_crawl: None, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    if not _TEST_DB:
        pytest.skip("SERYVON_TEST_DATABASE_URL not set (Postgres required)")
    engine = create_engine(_TEST_DB, future=True)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    session: Session = sessionmaker(bind=engine, expire_on_commit=False)()

    # Keep API integration tests deterministic: Celery dispatch is covered by
    # the task tests and must not leave background jobs touching this fixture's
    # tables while another test tears them down.
    monkeypatch.setattr(
        api_main.run_audit_task,
        "delay",
        lambda *args, **kwargs: SimpleNamespace(id="test-task-id"),
    )
    monkeypatch.setattr(
        api_main,
        "AsyncResult",
        lambda *args, **kwargs: SimpleNamespace(state="PENDING"),
    )

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
    assert resp.status_code == 202
    assert resp.json()["task_id"]
    assert resp.json()["status_url"].startswith("/audits/tasks/")
    assert resp.headers["location"].startswith("/audits/")


def test_create_then_get(db_client: TestClient) -> None:
    created = db_client.post("/audits", json={"url": "https://example.com"})
    assert created.status_code == 202
    task_id = created.json()["task_id"]
    fetched = db_client.get(f"/audits/tasks/{task_id}")
    assert fetched.status_code == 200
    assert fetched.json()["status"] in {"pending", "running", "done", "failed"}


def test_list_audits_history(db_client: TestClient) -> None:
    first = db_client.post("/audits", json={"url": "https://example.com"})
    second = db_client.post("/audits", json={"url": "https://example.com"})
    assert first.status_code == second.status_code == 202
    resp = db_client.get("/audits", params={"domain": "example.com"})
    assert resp.status_code == 200
    assert resp.json() == []


def test_list_domains_delegates_to_repository(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    expected = [SimpleNamespace(domain="example.com")]
    monkeypatch.setattr(api_main.repository, "list_domains", lambda _session: expected)
    assert api_main.list_domains(None) == expected  # type: ignore[arg-type]


def test_get_unknown_returns_404(db_client: TestClient) -> None:
    resp = db_client.get(f"/audits/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_create_audit_rejects_bad_url(db_client: TestClient) -> None:
    resp = db_client.post("/audits", json={"url": "not-a-url"})
    assert resp.status_code == 422


def test_compare_two_scorecards_exact(db_client: TestClient) -> None:
    """Unfinished async submissions are not yet comparable (M6)."""
    a = db_client.post("/audits", json={"url": "https://example.com"})
    b = db_client.post("/audits", json={"url": "https://example.com"})
    assert a.status_code == b.status_code == 202
    left = a.json()["task_id"]
    right = b.json()["task_id"]
    resp = db_client.post(
        "/scorecards/compare",
        json={"left_run_id": left, "right_run_id": right, "mode": "strict"},
    )
    assert resp.status_code == 422


def test_compare_unknown_run_returns_404(db_client: TestClient) -> None:
    resp = db_client.post(
        "/scorecards/compare",
        json={"left_run_id": str(uuid.uuid4()), "right_run_id": str(uuid.uuid4())},
    )
    assert resp.status_code == 404


def test_compare_returns_409_for_incomparable_profiles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from seryvon.scoring.comparison import Comparability, IncomparableError

    reports = {uuid.uuid4(): object(), uuid.uuid4(): object()}
    left_id, right_id = reports
    monkeypatch.setattr(api_main.repository, "load_report", lambda _s, run_id: reports.get(run_id))
    monkeypatch.setattr(
        api_main,
        "compare_scorecards",
        lambda *_args: (_ for _ in ()).throw(
            IncomparableError(
                Comparability.INCOMPATIBLE,
                api_main.ComparisonMode.STRICT,
                ["thresholds"],
                [api_main.ComparisonMode.DESCRIPTIVE],
            )
        ),
    )
    request = api_main.CompareRequest(left_run_id=left_id, right_run_id=right_id)
    with pytest.raises(api_main.HTTPException) as exc:
        api_main.compare(request, None)  # type: ignore[arg-type]
    assert exc.value.status_code == 409


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


def test_rank_tracking_happy_path(rank_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
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
