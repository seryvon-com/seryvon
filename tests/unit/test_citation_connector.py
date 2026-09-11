from __future__ import annotations

import httpx
import pytest

from seryvon.citation.connector import LlmConnector, rate_limit_snapshot, request_json


async def test_request_json_returns_payload_and_headers() -> None:
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"ok": True}, headers={"X-RateLimit-Remaining": "9"}
            )
        )
    )
    payload, headers = await request_json(
        "https://example.test", headers={}, json_body={}, client=client, timeout=1
    )
    await client.aclose()
    assert payload == {"ok": True}
    assert headers["x-ratelimit-remaining"] == "9"


async def test_request_json_raises_http_error() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(500)))
    with pytest.raises(httpx.HTTPStatusError):
        await request_json(
            "https://example.test", headers={}, json_body={}, client=client, timeout=1
        )
    await client.aclose()


def test_rate_limit_snapshot_filters_headers() -> None:
    assert rate_limit_snapshot(
        {"Retry-After": "2", "X-RateLimit-Remaining": "4", "Content-Type": "json"}
    ) == {"Retry-After": "2", "X-RateLimit-Remaining": "4"}


async def test_request_json_owns_and_closes_client(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def __init__(self) -> None:
            self.headers = {"retry-after": "1"}

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, bool]:
            return {"ok": True}

    class Client:
        closed = False

        def __init__(self, **_: object) -> None:
            pass

        async def post(self, *_args: object, **_kwargs: object) -> Response:
            return Response()

        async def aclose(self) -> None:
            self.closed = True

    monkeypatch.setattr(httpx, "AsyncClient", Client)
    payload, headers = await request_json(
        "https://example.test", headers={}, json_body={}, client=None, timeout=1
    )
    assert payload == {"ok": True}
    assert headers == {"retry-after": "1"}


def test_rate_limit_snapshot_ignores_unrelated_headers() -> None:
    assert rate_limit_snapshot({"content-type": "json", "server": "test"}) == {}


@pytest.mark.asyncio
async def test_connector_protocol_default_body_is_executable() -> None:
    class MinimalConnector(LlmConnector):
        provider = "test"

    assert await MinimalConnector().query("prompt") is None
