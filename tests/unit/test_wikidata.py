# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests du connecteur Wikidata + règle aso.brand_coherence."""

from __future__ import annotations

from typing import Any

import httpx

from seryvon.connectors.wikidata import (
    WikidataResult,
    brand_coherence,
    fetch_wikidata,
    parse_wikidata,
)
from seryvon.models.enums import Status
from seryvon.models.signals import ExternalSignals, SignalBundle
from seryvon.scoring.rules.aso import AsoBrandCoherenceCriterion

SAMPLE: dict[str, Any] = {
    "search": [
        {"id": "Q312", "label": "Apple Inc.", "description": "American technology company"},
    ]
}


# --------------------------------------------------------------------------- #
# parse_wikidata                                                              #
# --------------------------------------------------------------------------- #
def test_parse_found() -> None:
    result = parse_wikidata(SAMPLE)
    assert result.found is True
    assert result.entity_id == "Q312"
    assert result.label == "Apple Inc."


def test_parse_empty() -> None:
    assert parse_wikidata({"search": []}).found is False
    assert parse_wikidata({}).found is False


# --------------------------------------------------------------------------- #
# brand_coherence (pur)                                                       #
# --------------------------------------------------------------------------- #
def test_brand_coherence_match() -> None:
    result = WikidataResult(
        found=True, label="Apple Inc.", description="American technology company"
    )
    coherence = brand_coherence("Apple", "American technology company and devices", result)
    assert coherence == {"name": 1.0, "description": 1.0}


def test_brand_coherence_mismatch() -> None:
    result = WikidataResult(found=True, label="Banana Corp", description="Fruit distributor")
    coherence = brand_coherence("Apple", "Software and cloud services", result)
    assert coherence == {"name": 0.0, "description": 0.0}


# --------------------------------------------------------------------------- #
# fetch_wikidata (MockTransport)                                              #
# --------------------------------------------------------------------------- #
async def test_fetch_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["search"] == "Apple"
        return httpx.Response(200, json=SAMPLE)

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    result = await fetch_wikidata("Apple", client=client)
    await client.aclose()
    assert result.entity_id == "Q312"


async def test_fetch_error_returns_empty() -> None:
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500)))
    result = await fetch_wikidata("Apple", client=client)
    await client.aclose()
    assert result == WikidataResult()


# --------------------------------------------------------------------------- #
# aso.brand_coherence                                                         #
# --------------------------------------------------------------------------- #
def test_brand_coherence_rule_scored() -> None:
    bundle = SignalBundle(
        domain="ex.com",
        external=ExternalSignals(brand_coherence={"name": 1.0, "description": 0.0}),
    )
    result = AsoBrandCoherenceCriterion().evaluate(bundle)
    assert result.score == 50.0
    assert result.pillars == ["aso", "aeo"]


def test_brand_coherence_rule_not_measured() -> None:
    assert (
        AsoBrandCoherenceCriterion().evaluate(SignalBundle(domain="ex.com")).status
        is Status.NOT_MEASURED
    )
