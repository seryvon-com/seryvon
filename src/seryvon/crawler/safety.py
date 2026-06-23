# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""SSRF guard for user-controlled fetches (SIC doc 10 §2).

Every URL the crawler resolves comes from an untrusted source (the audited
domain, its robots.txt, its sitemaps, its in-page links). Without a guard, an
audit of `http://169.254.169.254/…` or a redirect to `http://127.0.0.1:6379/`
would reach internal infrastructure. This module enforces, per SIC doc 10 §2:

- scheme allow-list (`http`/`https` only);
- rejection of URL userinfo (`user:pass@host`);
- DNS resolution via an injectable resolver, then blocking of private,
  loopback, link-local, multicast and reserved IPv4/IPv6 (incl. IPv4-mapped);
- a small block-list of known cloud-metadata hostnames (defence in depth);
- per-hop re-validation on redirects, capped at `MAX_REDIRECTS` (5).

`UnsafeUrlError` subclasses `httpx.HTTPError` so the existing graceful-degradation
paths (crawl suppresses `httpx.HTTPError`, discovery catches it) skip an unsafe
target without aborting the audit (ENF-03) — and crucially without connecting to
it. The DNS resolver is injectable so unit tests run offline and deterministically.

Residual gap (documented): the resolve→connect window leaves a narrow DNS-rebinding
surface (we validate the resolved IPs, then let httpx re-resolve to connect). Full
socket pinning to the validated IP is deferred; the IP block-list still rejects any
hop whose resolution lands on a private range at validation time.
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from collections.abc import Callable
from urllib.parse import urlsplit

import httpx

ALLOWED_SCHEMES = frozenset({"http", "https"})

# Known cloud-metadata hostnames. The metadata IPs (169.254.169.254, fd00:ec2::254)
# are already covered by the link-local/private checks; these names are blocked too
# in case they ever resolve to a routable address (defence in depth).
BLOCKED_HOSTNAMES = frozenset({"metadata.google.internal", "metadata.goog"})

#: Maximum redirect hops, each re-validated (SIC doc 10 §2).
MAX_REDIRECTS = 5

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})

#: Resolve a hostname to a list of IP strings (injectable for offline tests).
Resolver = Callable[[str], list[str]]


class UnsafeUrlError(httpx.HTTPError):
    """A URL was rejected by the SSRF guard (subclasses HTTPError for graceful skip)."""


def _default_resolver(host: str) -> list[str]:
    """Resolve `host` to its IP addresses via the system resolver."""
    infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    return [str(info[4][0]) for info in infos]


def _ip_is_blocked(ip: str) -> bool:
    """True if `ip` falls in a non-public range we must never connect to."""
    try:
        addr: ipaddress.IPv4Address | ipaddress.IPv6Address = ipaddress.ip_address(ip)
    except ValueError:
        # Unparseable address from the resolver — treat as unsafe.
        return True
    # Unwrap IPv4-mapped IPv6 (e.g. ::ffff:169.254.169.254) before checking.
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped is not None:
        addr = addr.ipv4_mapped
    return (
        addr.is_private
        or addr.is_loopback
        or addr.is_link_local
        or addr.is_multicast
        or addr.is_reserved
        or addr.is_unspecified
        or not addr.is_global
    )


def validate_url(url: str, *, resolver: Resolver = _default_resolver) -> None:
    """Raise `UnsafeUrlError` if `url` must not be fetched (SIC doc 10 §2).

    Pure except for the DNS lookup, which goes through the injectable `resolver`.
    Checks scheme, userinfo, the metadata host-list, then every resolved IP.
    """
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in ALLOWED_SCHEMES:
        raise UnsafeUrlError(f"scheme not allowed: {scheme or '(none)'!r}")
    if parts.username or parts.password:
        raise UnsafeUrlError("URL userinfo (user:pass@) is not allowed")
    host = (parts.hostname or "").lower().rstrip(".")
    if not host:
        raise UnsafeUrlError("URL has no host")
    if host in BLOCKED_HOSTNAMES:
        raise UnsafeUrlError(f"blocked metadata hostname: {host}")

    # An IP literal is checked directly; a name is resolved and every answer checked.
    try:
        ipaddress.ip_address(host)
        candidates = [host]
    except ValueError:
        try:
            candidates = resolver(host)
        except OSError as exc:
            raise UnsafeUrlError(f"cannot resolve host: {host}") from exc
        if not candidates:
            raise UnsafeUrlError(f"host did not resolve: {host}") from None

    for ip in candidates:
        if _ip_is_blocked(ip):
            raise UnsafeUrlError(f"host {host} resolves to a non-public address: {ip}")


async def assert_url_safe(url: str, *, resolver: Resolver = _default_resolver) -> None:
    """Async wrapper around `validate_url` (DNS lookup runs off the event loop)."""
    await asyncio.to_thread(validate_url, url, resolver=resolver)


async def safe_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_redirects: int = MAX_REDIRECTS,
    resolver: Resolver = _default_resolver,
) -> tuple[httpx.Response, int]:
    """GET `url` with per-hop SSRF validation and a bounded redirect chain.

    Returns `(final_response, redirect_count)`. The `client` MUST be created with
    `follow_redirects=False`: redirects are followed manually here so each hop's
    destination is re-validated before any connection is made. Raises
    `UnsafeUrlError` on an unsafe hop or when the chain exceeds `max_redirects`.
    """
    current = url
    redirects = 0
    while True:
        await assert_url_safe(current, resolver=resolver)
        response = await client.get(current)
        if response.status_code not in _REDIRECT_STATUSES:
            return response, redirects
        location = response.headers.get("location")
        if not location:
            return response, redirects
        if redirects >= max_redirects:
            raise UnsafeUrlError(f"too many redirects (> {max_redirects})")
        current = str(httpx.URL(str(response.url)).join(location))
        redirects += 1


# Re-export hint for callers wiring their own fetch loops.
__all__ = [
    "ALLOWED_SCHEMES",
    "BLOCKED_HOSTNAMES",
    "MAX_REDIRECTS",
    "Resolver",
    "UnsafeUrlError",
    "assert_url_safe",
    "safe_get",
    "validate_url",
]
