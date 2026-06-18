# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Règles du pilier GEO (Generative Engine Optimization), document 04 §3.

Cœur GEO on-page (Phase 2.6) : `geo.ssr` (heuristique render_mode, D10),
`noise_ratio`, `entity_density`, `primary_sources`, `authors`, `cross_platform`,
`freshness`. La fraîcheur lit `SignalBundle.audited_at` (référence figée, DG2 →
déterminisme). Les critères de citation LLM (`geo.citation_*`) arrivent en Phase 3.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import ClassVar

from seryvon.models.criterion import Criterion, CriterionResult, ThresholdConfig, register
from seryvon.models.enums import status_from_score
from seryvon.models.signals import SignalBundle

# Seuils du cœur GEO on-page (document 04 §3).
_NOISE_RATIO_TARGET = 0.20
_ENTITY_DENSITY_MIN = 0.02
_ENTITY_DENSITY_MAX = 0.20
_CROSS_PLATFORM_TARGET = 4
_FRESH_DAYS = 90
_STALE_DAYS = 365


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def _parse_date(value: str) -> date | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


@register
class GeoSsrCriterion(Criterion):
    """Rendu SSR vs CSR (`geo.ssr`) : part des pages servies en rendu serveur."""

    key = "geo.ssr"
    pillars: ClassVar[list[str]] = ["geo", "aeo", "aso"]
    weight = 1.8

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        modes = [p.render_mode for p in signals.pages if p.render_mode]
        if not modes:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Mode de rendu indisponible."
            )
        ssr = sum(1 for mode in modes if mode == "ssr")
        score = round(ssr / len(modes) * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"pages": len(modes), "ssr": ssr},
            score=score,
            status=status_from_score(score),
            threshold={"target": "100% SSR"},
            explanation=f"{ssr}/{len(modes)} page(s) en rendu serveur (heuristique M2).",
            evidence={"source": "heuristique SSR/CSR (M2)"},
            weight=self.weight,
        )


@register
class GeoNoiseRatioCriterion(Criterion):
    """Ratio contenu/bruit (`geo.noise_ratio`) : ≥ 0.20 = optimal."""

    key = "geo.noise_ratio"
    pillars: ClassVar[list[str]] = ["geo"]
    weight = 0.8

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        ratios = [p.main_text_ratio for p in signals.pages if p.main_text_ratio is not None]
        if not ratios:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Ratio contenu/bruit indisponible."
            )
        scores = [
            100.0 if r >= _NOISE_RATIO_TARGET else round(r / _NOISE_RATIO_TARGET * 100, 2)
            for r in ratios
        ]
        score = _mean(scores)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"pages": len(ratios), "mean_ratio": round(_mean(ratios) / 100, 4)},
            score=score,
            status=status_from_score(score),
            threshold={"min_ratio": _NOISE_RATIO_TARGET},
            explanation=f"Ratio contenu/bruit moyen sur {len(ratios)} page(s).",
            evidence={"source": "HTML (contenu principal)"},
            weight=self.weight,
        )


@register
class GeoEntityDensityCriterion(Criterion):
    """Densité d'entités (`geo.entity_density`) : normalisée sur plage cible (heuristique)."""

    key = "geo.entity_density"
    pillars: ClassVar[list[str]] = ["geo"]
    weight = 1.0

    def _score_page(self, entity_count: int, word_count: int) -> float:
        density = entity_count / word_count
        if density < _ENTITY_DENSITY_MIN:
            return round(density / _ENTITY_DENSITY_MIN * 100, 2)
        if density <= _ENTITY_DENSITY_MAX:
            return 100.0
        return 60.0  # trop dense (probable bruit/listes)

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        pages = [p for p in signals.pages if p.word_count > 0]
        if not pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Aucune page avec contenu textuel."
            )
        score = _mean([self._score_page(p.entity_count, p.word_count) for p in pages])
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"pages": len(pages)},
            score=score,
            status=status_from_score(score),
            threshold={"min": _ENTITY_DENSITY_MIN, "max": _ENTITY_DENSITY_MAX},
            explanation=f"Densité d'entités estimée sur {len(pages)} page(s) (heuristique).",
            evidence={"source": "heuristique entités (M3.3)"},
            weight=self.weight,
        )


@register
class GeoPrimarySourcesCriterion(Criterion):
    """Sources primaires (`geo.primary_sources`) : ≥1 lien sortant par page (tag aeo)."""

    key = "geo.primary_sources"
    pillars: ClassVar[list[str]] = ["geo", "aeo"]
    weight = 1.2

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        pages = signals.pages
        if not pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Aucune page crawlée."
            )
        with_sources = sum(1 for p in pages if p.external_link_domains)
        score = round(with_sources / len(pages) * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"pages": len(pages), "with_sources": with_sources},
            score=score,
            status=status_from_score(score),
            threshold={"min": "≥1 source sortante par page"},
            explanation=f"{with_sources}/{len(pages)} page(s) citent une source externe.",
            evidence={"source": "liens sortants"},
            weight=self.weight,
        )


@register
class GeoAuthorsCriterion(Criterion):
    """Auteurs identifiables (`geo.authors`) : présence d'un auteur structuré (tag aeo)."""

    key = "geo.authors"
    pillars: ClassVar[list[str]] = ["geo", "aeo"]
    weight = 1.2

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        pages = signals.pages
        if not pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Aucune page crawlée."
            )
        present = any(p.has_author for p in pages)
        score = 100.0 if present else 0.0
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"has_author": present},
            score=score,
            status=status_from_score(score),
            threshold={"structured": "author/Person en JSON-LD"},
            explanation="Auteur structuré présent." if present else "Aucun auteur structuré.",
            evidence={"source": "JSON-LD"},
            weight=self.weight,
        )


@register
class GeoCrossPlatformCriterion(Criterion):
    """Présence cross-plateforme (`geo.cross_platform`) : ≥4 plateformes = 100 (tag aso)."""

    key = "geo.cross_platform"
    pillars: ClassVar[list[str]] = ["geo", "aso"]
    weight = 1.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        pages = signals.pages
        if not pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Aucune page crawlée."
            )
        platforms = sorted({platform for p in pages for platform in p.social_platforms})
        score = round(min(100.0, len(platforms) / _CROSS_PLATFORM_TARGET * 100), 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"platforms": platforms},
            score=score,
            status=status_from_score(score),
            threshold={"target": _CROSS_PLATFORM_TARGET},
            explanation=f"{len(platforms)} plateforme(s) liée(s) : {platforms or 'aucune'}.",
            evidence={"source": "sameAs + liens sociaux"},
            weight=self.weight,
        )


@register
class GeoFreshnessCriterion(Criterion):
    """Fraîcheur (`geo.freshness`) : contenu < 90 j = optimal (tag aeo).

    Âge calculé vs `SignalBundle.audited_at` (référence figée, déterminisme DG2).
    """

    key = "geo.freshness"
    pillars: ClassVar[list[str]] = ["geo", "aeo"]
    weight = 1.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        if signals.audited_at is None:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Date de référence d'audit indisponible."
            )
        dates = [d for p in signals.pages if p.content_date and (d := _parse_date(p.content_date))]
        if not dates:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Aucune date de contenu structurée."
            )
        age = (signals.audited_at.date() - max(dates)).days
        score = 100.0 if age < _FRESH_DAYS else 50.0 if age < _STALE_DAYS else 0.0
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"age_days": age, "latest": max(dates).isoformat()},
            score=score,
            status=status_from_score(score),
            threshold={"fresh_days": _FRESH_DAYS},
            explanation=f"Contenu le plus récent daté de {age} jour(s).",
            evidence={"source": "dates JSON-LD vs date d'audit"},
            weight=self.weight,
        )
