# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests des règles authority.* (OpenPageRank + backlinks)."""

from __future__ import annotations

from seryvon.models.enums import Status
from seryvon.models.signals import ExternalSignals, SignalBundle
from seryvon.scoring.rules.authority import AuthorityBacklinksCriterion, AuthorityOprCriterion


def _bundle(opr: float | None = None, referring: int | None = None) -> SignalBundle:
    return SignalBundle(
        domain="ex.com",
        external=ExternalSignals(open_page_rank=opr, referring_domains=referring),
    )


def test_opr_scaled_by_ten() -> None:
    assert AuthorityOprCriterion().evaluate(_bundle(opr=4.27)).score == 42.7
    assert AuthorityOprCriterion().evaluate(_bundle(opr=9.0)).score == 90.0


def test_opr_not_measured_without_key() -> None:
    result = AuthorityOprCriterion().evaluate(_bundle(opr=None))
    assert result.status is Status.NOT_MEASURED


def test_backlinks_not_measured_by_default() -> None:
    # v0.1 : aucune source de domaines référents -> referring_domains None (D3).
    result = AuthorityBacklinksCriterion().evaluate(_bundle())
    assert result.status is Status.NOT_MEASURED


def test_backlinks_log_scale_when_present() -> None:
    # La règle est prête pour un futur connecteur : échelle log.
    assert AuthorityBacklinksCriterion().evaluate(_bundle(referring=0)).score == 0.0
    assert AuthorityBacklinksCriterion().evaluate(_bundle(referring=100)).score == 50.11
    assert AuthorityBacklinksCriterion().evaluate(_bundle(referring=10000)).score == 100.0
