# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests for the perf.* rules (Core Web Vitals + Lighthouse) across their tiers."""

from __future__ import annotations

from seryvon.models.enums import Status
from seryvon.models.signals import ExternalSignals, SignalBundle
from seryvon.scoring.rules.perf import (
    PerfClsCriterion,
    PerfInpCriterion,
    PerfLcpCriterion,
    PerfLighthouseCriterion,
)


def _bundle(cwv: dict[str, float] | None = None, lighthouse: float | None = None) -> SignalBundle:
    return SignalBundle(
        domain="ex.com",
        external=ExternalSignals(core_web_vitals=cwv, lighthouse_performance=lighthouse),
    )


def test_lcp_bands() -> None:
    assert PerfLcpCriterion().evaluate(_bundle({"lcp": 2000})).score == 100
    assert PerfLcpCriterion().evaluate(_bundle({"lcp": 3000})).score == 50
    assert PerfLcpCriterion().evaluate(_bundle({"lcp": 5000})).score == 0


def test_cls_bands() -> None:
    assert PerfClsCriterion().evaluate(_bundle({"cls": 0.05})).score == 100
    assert PerfClsCriterion().evaluate(_bundle({"cls": 0.2})).score == 50
    assert PerfClsCriterion().evaluate(_bundle({"cls": 0.4})).score == 0


def test_inp_bands() -> None:
    assert PerfInpCriterion().evaluate(_bundle({"inp": 150})).score == 100
    assert PerfInpCriterion().evaluate(_bundle({"inp": 300})).score == 50
    assert PerfInpCriterion().evaluate(_bundle({"inp": 700})).score == 0


def test_cwv_not_measured_without_data() -> None:
    assert PerfLcpCriterion().evaluate(_bundle(None)).status is Status.NOT_MEASURED
    # Field data present but without the target metric -> not_measured as well.
    assert PerfInpCriterion().evaluate(_bundle({"lcp": 2000})).status is Status.NOT_MEASURED


def test_lighthouse_score() -> None:
    result = PerfLighthouseCriterion().evaluate(_bundle(lighthouse=0.92))
    assert result.score == 92.0
    assert result.status is Status.OK


def test_lighthouse_not_measured() -> None:
    assert PerfLighthouseCriterion().evaluate(_bundle()).status is Status.NOT_MEASURED
