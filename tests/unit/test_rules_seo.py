# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests de la règle SEO `meta.title` — tous les paliers de seuils."""

from __future__ import annotations

from seryvon.models.enums import Status
from seryvon.models.signals import PageSignals, SignalBundle
from seryvon.scoring.rules.seo import MetaTitleCriterion


def _bundle(title: str | None) -> SignalBundle:
    return SignalBundle(domain="ex.com", pages=[PageSignals(url="https://ex.com/", title=title)])


def test_title_optimal_scores_100() -> None:
    result = MetaTitleCriterion().evaluate(_bundle("Un titre de longueur tout à fait correcte"))
    assert result.score == 100.0
    assert result.status is Status.OK


def test_title_absent_scores_0() -> None:
    result = MetaTitleCriterion().evaluate(_bundle(None))
    assert result.score == 0.0
    assert result.status is Status.CRITICAL


def test_title_too_short() -> None:
    result = MetaTitleCriterion().evaluate(_bundle("Trop court"))
    assert result.score == 60.0
    assert result.status is Status.WARNING


def test_title_too_long() -> None:
    long_title = (
        "Un titre vraiment beaucoup trop long qui dépasse la limite recommandée de soixante"
    )
    result = MetaTitleCriterion().evaluate(_bundle(long_title))
    assert result.score == 70.0
    assert result.status is Status.WARNING


def test_title_result_is_traceable() -> None:
    result = MetaTitleCriterion().evaluate(_bundle("Un titre de longueur tout à fait correcte"))
    assert result.threshold == {"min": 30, "max": 60}
    assert result.evidence.get("source")
    assert result.pillars == ["seo"]


def test_no_page_yields_zero() -> None:
    empty = SignalBundle(domain="ex.com", pages=[])
    result = MetaTitleCriterion().evaluate(empty)
    assert result.score == 0.0
