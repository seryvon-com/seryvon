# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Catalogue des règles de scoring du pilier SEO (document 04, §2).

Agrégation multi-pages :
- critères *page-level* (title, description, h1, schema…) : score = moyenne des
  scores par page (`PageCriterion`) ; `not_measured` si aucune page crawlée ;
- critères *site-level* (unicité des titles, orphelines, indexabilité, HTTPS,
  sitemap, alt) : calcul direct sur l'ensemble du crawl.

Déterminisme : `evaluate()` ne lit que le `SignalBundle` (aucune I/O) ; toutes
les sorties (listes d'évidence) sont triées. Les critères `perf.*` (PSI) et
`authority.*` (OpenPageRank) arrivent aux étapes 5/6.

Limitation connue : seuls les seuils par défaut (ci-dessous) sont appliqués ; la
surcharge `thresholds:` du YAML n'est pas encore câblée (seul
`criteria_overrides.weight` l'est, via le moteur). Tags multi-piliers
(struct.schema → gso/aeo/aso, perf → gso) ajoutés quand ces piliers seront
implémentés (Phase 2).
"""

from __future__ import annotations

from collections.abc import Callable
from itertools import pairwise
from typing import Any, ClassVar

from seryvon.models.criterion import Criterion, CriterionResult, ThresholdConfig, register
from seryvon.models.enums import STATUS_OK_THRESHOLD, status_from_score
from seryvon.models.signals import PageSignals, SignalBundle

# Seuils par défaut (document 04, §2).
TITLE_MIN_LEN, TITLE_MAX_LEN = 30, 60
DESC_MIN_LEN, DESC_MAX_LEN = 120, 158
CONTENT_MIN_WORDS = 800
TEXT_RATIO_MIN = 0.15
LINKS_MIN, LINKS_MAX = 3, 100
MAX_REDIRECT_HOPS = 1
OG_REQUIRED = ("og:title", "og:description", "og:image", "og:url", "og:type")
TWITTER_FIELDS = ("twitter:card", "twitter:title", "twitter:description", "twitter:image")

_EVIDENCE_HTML: dict[str, Any] = {"source": "HTML parsing"}
_MAX_EVIDENCE = 10  # nombre max d'URLs listées en évidence


def _mean(values: list[float]) -> float:
    """Moyenne arrondie d'une liste de scores (0.0 si vide)."""
    return round(sum(values) / len(values), 2) if values else 0.0


def _is_indexable(meta_robots: str | None) -> bool:
    """Indexable si aucune directive `noindex` n'est présente."""
    return meta_robots is None or "noindex" not in meta_robots.lower()


# --------------------------------------------------------------------------- #
# Base des critères page-level                                                 #
# --------------------------------------------------------------------------- #
class PageCriterion(Criterion):
    """Critère évalué par page ; score d'audit = moyenne des scores par page.

    Sous-classer et implémenter `score_page` (formule du document 04).
    `not_measured` si aucune page n'a été crawlée.
    """

    threshold: ClassVar[dict[str, Any]] = {}
    label: ClassVar[str] = ""

    def score_page(self, page: PageSignals) -> float:
        raise NotImplementedError

    def _aggregate(
        self,
        signals: SignalBundle,
        score_page: Callable[[PageSignals], float],
        *,
        threshold: dict[str, Any] | None = None,
    ) -> CriterionResult:
        """Moyenne des scores par page + évidence des pages non conformes."""
        pages = signals.pages
        if not pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Aucune page crawlée."
            )
        scores = [score_page(page) for page in pages]
        score = _mean(scores)
        passing = sum(1 for s in scores if s >= STATUS_OK_THRESHOLD)
        failing = sorted(
            page.url for page, s in zip(pages, scores, strict=True) if s < STATUS_OK_THRESHOLD
        )
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"pages": len(pages), "passing": passing, "mean_score": score},
            score=score,
            status=status_from_score(score),
            threshold=dict(self.threshold if threshold is None else threshold),
            explanation=f"{self.label} : {passing}/{len(pages)} page(s) conforme(s) "
            f"(score moyen {score}).",
            evidence={**_EVIDENCE_HTML, "non_conformes": failing[:_MAX_EVIDENCE]},
            weight=self.weight,
        )

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        return self._aggregate(signals, self.score_page)


# --------------------------------------------------------------------------- #
# Métadonnées                                                                  #
# --------------------------------------------------------------------------- #
@register
class MetaTitleCriterion(PageCriterion):
    """Présence et longueur de la balise <title> (`meta.title`)."""

    key = "meta.title"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.5
    label = "Balise title"
    threshold: ClassVar[dict[str, Any]] = {"min": TITLE_MIN_LEN, "max": TITLE_MAX_LEN}

    def score_page(self, page: PageSignals) -> float:
        title = page.title
        if not title:
            return 0.0
        length = len(title)
        if TITLE_MIN_LEN <= length <= TITLE_MAX_LEN:
            return 100.0
        return 60.0 if length < TITLE_MIN_LEN else 70.0


@register
class MetaDescriptionCriterion(PageCriterion):
    """Présence et longueur de la meta description (`meta.description`)."""

    key = "meta.description"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.2
    label = "Meta description"
    threshold: ClassVar[dict[str, Any]] = {"min": DESC_MIN_LEN, "max": DESC_MAX_LEN}

    def score_page(self, page: PageSignals) -> float:
        desc = page.meta_description
        if not desc:
            return 0.0
        length = len(desc)
        if DESC_MIN_LEN <= length <= DESC_MAX_LEN:
            return 100.0
        return 60.0


@register
class MetaCanonicalCriterion(PageCriterion):
    """Présence et validité de la balise canonical (`meta.canonical`)."""

    key = "meta.canonical"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.0
    label = "Canonical"
    threshold: ClassVar[dict[str, Any]] = {"valid": "URL absolue http(s)"}

    def score_page(self, page: PageSignals) -> float:
        canonical = page.canonical
        if not canonical:
            return 0.0
        return 100.0 if canonical.startswith(("http://", "https://")) else 70.0


@register
class MetaRobotsCriterion(PageCriterion):
    """Directive meta robots : la page est-elle indexable (`meta.robots`) ?"""

    key = "meta.robots"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.0
    label = "Meta robots"
    threshold: ClassVar[dict[str, Any]] = {"indexable": "pas de noindex"}

    def score_page(self, page: PageSignals) -> float:
        return 100.0 if _is_indexable(page.meta_robots) else 0.0


@register
class MetaTitleUniqueCriterion(Criterion):
    """Unicité des titles sur l'ensemble des pages (`meta.title_unique`)."""

    key = "meta.title_unique"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        titles = [p.title for p in signals.pages if p.title]
        if not titles:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Aucun title à comparer."
            )
        unique = len({t.strip().lower() for t in titles})
        score = round(unique / len(titles) * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"titled_pages": len(titles), "unique": unique},
            score=score,
            status=status_from_score(score),
            threshold={"target": "100% de titles uniques"},
            explanation=f"{unique} title(s) unique(s) sur {len(titles)} page(s) titrée(s).",
            evidence=_EVIDENCE_HTML,
            weight=self.weight,
        )


# --------------------------------------------------------------------------- #
# Métadonnées sociales                                                         #
# --------------------------------------------------------------------------- #
@register
class OpenGraphCriterion(PageCriterion):
    """Complétude des balises Open Graph (`og.complete`)."""

    key = "og.complete"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 0.6
    label = "Open Graph"
    threshold: ClassVar[dict[str, Any]] = {"required": list(OG_REQUIRED)}

    def score_page(self, page: PageSignals) -> float:
        present = sum(1 for key in OG_REQUIRED if page.open_graph.get(key))
        return round(present / len(OG_REQUIRED) * 100, 2)


@register
class TwitterCardCriterion(PageCriterion):
    """Présence des Twitter Cards (`twitter.cards`)."""

    key = "twitter.cards"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 0.4
    label = "Twitter Cards"
    threshold: ClassVar[dict[str, Any]] = {"complete": "≥3 champs", "partial": "≥1 champ"}

    def score_page(self, page: PageSignals) -> float:
        present = sum(1 for key in TWITTER_FIELDS if page.twitter_card.get(key))
        if present >= 3:
            return 100.0
        return 50.0 if present >= 1 else 0.0


# --------------------------------------------------------------------------- #
# Structure sémantique                                                         #
# --------------------------------------------------------------------------- #
@register
class StructH1Criterion(PageCriterion):
    """Unicité du H1 (`struct.h1`) : exactement un par page."""

    key = "struct.h1"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.0
    label = "H1 unique"
    threshold: ClassVar[dict[str, Any]] = {"expected": 1}

    def score_page(self, page: PageSignals) -> float:
        if page.h1_count == 1:
            return 100.0
        return 50.0 if page.h1_count > 1 else 0.0


@register
class StructHierarchyCriterion(PageCriterion):
    """Cohérence de la hiérarchie Hn (`struct.hierarchy`).

    Cohérente = exactement un H1 et aucun niveau sauté (h2 -> h4 interdit).
    """

    key = "struct.hierarchy"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 0.8
    label = "Hiérarchie Hn"
    threshold: ClassVar[dict[str, Any]] = {"rule": "1 H1, aucun niveau sauté"}

    def score_page(self, page: PageSignals) -> float:
        levels = sorted(int(tag[1]) for tag in page.headings)
        if not levels:
            return 0.0
        if page.h1_count != 1 or levels[0] != 1:
            return 50.0
        no_gap = all(b - a <= 1 for a, b in pairwise(levels))
        return 100.0 if no_gap else 50.0


# --------------------------------------------------------------------------- #
# Contenu                                                                      #
# --------------------------------------------------------------------------- #
@register
class ContentDepthCriterion(PageCriterion):
    """Profondeur de contenu (`content.depth`) : ≥ 800 mots = optimal."""

    key = "content.depth"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.3
    label = "Profondeur de contenu"
    threshold: ClassVar[dict[str, Any]] = {"min_words": CONTENT_MIN_WORDS}

    @staticmethod
    def _target_words(thresholds: ThresholdConfig | None) -> float:
        """Seuil de mots : surcharge `content.depth.target_words` ou défaut 800."""
        section = thresholds.get("content.depth") if thresholds else None
        value = section.get("target_words") if section else None
        if isinstance(value, int | float) and value > 0:
            return float(value)
        return float(CONTENT_MIN_WORDS)

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        target = self._target_words(thresholds)
        return self._aggregate(
            signals,
            lambda page: round(min(100.0, page.word_count / target * 100), 2),
            threshold={"min_words": int(target)},
        )


@register
class ContentTextRatioCriterion(PageCriterion):
    """Ratio texte/code (`content.text_ratio`) : ≥ 0.15 = optimal."""

    key = "content.text_ratio"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 0.6
    label = "Ratio texte/code"
    threshold: ClassVar[dict[str, Any]] = {"min_ratio": TEXT_RATIO_MIN}

    def score_page(self, page: PageSignals) -> float:
        ratio = page.text_ratio
        if ratio is None:
            return 0.0
        return round(min(100.0, ratio / TEXT_RATIO_MIN * 100), 2)


@register
class StructSchemaCriterion(PageCriterion):
    """Présence de données structurées JSON-LD (`struct.schema`).

    Tags multi-piliers (gso/aeo/aso) ajoutés en Phase 2 ; seo seul en Phase 1.
    """

    key = "struct.schema"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.5
    label = "Données structurées"
    threshold: ClassVar[dict[str, Any]] = {"min_types": 1}

    def score_page(self, page: PageSignals) -> float:
        return 100.0 if page.structured_data_types else 0.0


# --------------------------------------------------------------------------- #
# Maillage interne                                                             #
# --------------------------------------------------------------------------- #
@register
class LinksInternalCriterion(PageCriterion):
    """Volume de liens internes par page (`links.internal`) : 3 à 100."""

    key = "links.internal"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 0.8
    label = "Maillage interne"
    threshold: ClassVar[dict[str, Any]] = {"min": LINKS_MIN, "max": LINKS_MAX}

    def score_page(self, page: PageSignals) -> float:
        count = page.internal_links
        if LINKS_MIN <= count <= LINKS_MAX:
            return 100.0
        if count == 0:
            return 0.0
        return 60.0  # trop peu (< 3) ou trop (> 100)


@register
class LinksOrphansCriterion(Criterion):
    """Pages orphelines (`links.orphans`) : sans lien interne entrant.

    `not_measured` si moins de deux pages (pas de maillage à évaluer). La home
    (première page) n'est jamais considérée orpheline.
    """

    key = "links.orphans"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 0.7

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        pages = signals.pages
        if len(pages) < 2:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Maillage non évaluable (< 2 pages)."
            )
        linked: set[str] = set()
        for page in pages:
            linked.update(page.internal_link_targets)
        non_home = pages[1:]
        orphans = sorted(p.url for p in non_home if p.url not in linked)
        score = round(100 - len(orphans) / len(non_home) * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"pages": len(pages), "orphans": len(orphans)},
            score=score,
            status=status_from_score(score),
            threshold={"target": "0 page orpheline"},
            explanation=f"{len(orphans)} page(s) orpheline(s) sur {len(non_home)} (hors home).",
            evidence={**_EVIDENCE_HTML, "orphelines": orphans[:_MAX_EVIDENCE]},
            weight=self.weight,
        )


# --------------------------------------------------------------------------- #
# Accessibilité technique                                                      #
# --------------------------------------------------------------------------- #
@register
class ImgAltCriterion(Criterion):
    """Couverture des attributs alt (`img.alt`) : % d'images avec alt.

    `not_measured` si le site ne contient aucune image.
    """

    key = "img.alt"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 0.5

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        total = sum(p.images_total for p in signals.pages)
        if total == 0:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Aucune image à évaluer."
            )
        with_alt = sum(p.images_with_alt for p in signals.pages)
        score = round(with_alt / total * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"images": total, "with_alt": with_alt},
            score=score,
            status=status_from_score(score),
            threshold={"target": "100% d'images avec alt"},
            explanation=f"{with_alt}/{total} image(s) avec attribut alt.",
            evidence=_EVIDENCE_HTML,
            weight=self.weight,
        )


# --------------------------------------------------------------------------- #
# Crawl & indexabilité                                                         #
# --------------------------------------------------------------------------- #
@register
class CrawlIndexableCriterion(Criterion):
    """Indexabilité (`crawl.indexable`) : % de pages HTTP 200 et sans noindex."""

    key = "crawl.indexable"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.2

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        pages = signals.pages
        if not pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Aucune page crawlée."
            )
        indexable = sum(1 for p in pages if p.status_code == 200 and _is_indexable(p.meta_robots))
        score = round(indexable / len(pages) * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"pages": len(pages), "indexable": indexable},
            score=score,
            status=status_from_score(score),
            threshold={"target": "100% indexables (200, pas de noindex)"},
            explanation=f"{indexable}/{len(pages)} page(s) indexable(s).",
            evidence=_EVIDENCE_HTML,
            weight=self.weight,
        )


@register
class CrawlSitemapCriterion(Criterion):
    """Présence et validité d'un sitemap (`crawl.sitemap`)."""

    key = "crawl.sitemap"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 0.8

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        valid = signals.site.sitemap_valid
        score = 100.0 if valid else 0.0
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={
                "sitemap_valid": valid,
                "url_count": signals.site.sitemap_url_count,
            },
            score=score,
            status=status_from_score(score),
            threshold={"valid": "sitemap récupéré et bien formé"},
            explanation=(
                f"Sitemap valide ({signals.site.sitemap_url_count} URLs)."
                if valid
                else "Aucun sitemap valide trouvé."
            ),
            evidence={"source": "M1 Discovery"},
            weight=self.weight,
        )


@register
class CrawlHttpsCriterion(Criterion):
    """Sécurisation HTTPS (`crawl.https`) : % de pages servies en HTTPS."""

    key = "crawl.https"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        pages = signals.pages
        if not pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, "Aucune page crawlée."
            )
        https = sum(1 for p in pages if p.url.startswith("https://"))
        score = round(https / len(pages) * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"pages": len(pages), "https": https},
            score=score,
            status=status_from_score(score),
            threshold={"target": "100% HTTPS"},
            explanation=f"{https}/{len(pages)} page(s) en HTTPS.",
            evidence=_EVIDENCE_HTML,
            weight=self.weight,
        )


@register
class CrawlRedirectsCriterion(PageCriterion):
    """Chaînes de redirection (`crawl.redirects`) : ≤ 1 saut = optimal."""

    key = "crawl.redirects"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 0.5
    label = "Chaînes de redirection"
    threshold: ClassVar[dict[str, Any]] = {"max_hops": MAX_REDIRECT_HOPS}

    def score_page(self, page: PageSignals) -> float:
        if page.redirects <= MAX_REDIRECT_HOPS:
            return 100.0
        return 50.0 if page.redirects <= 3 else 0.0


# --------------------------------------------------------------------------- #
# Internationalisation                                                         #
# --------------------------------------------------------------------------- #
@register
class HreflangCriterion(Criterion):
    """Cohérence hreflang (`i18n.hreflang`).

    `not_measured` si aucun hreflang n'est déclaré (site monolingue présumé,
    décision validée). Sinon : cohérent si `x-default` est présent.
    """

    key = "i18n.hreflang"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 0.5

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        with_hreflang = [p for p in signals.pages if p.hreflang]
        if not with_hreflang:
            return CriterionResult.not_measured(
                self.key,
                self.pillars,
                self.weight,
                "Aucun hreflang déclaré (site monolingue présumé).",
            )
        scores = [100.0 if "x-default" in p.hreflang else 70.0 for p in with_hreflang]
        score = _mean(scores)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"pages_with_hreflang": len(with_hreflang)},
            score=score,
            status=status_from_score(score),
            threshold={"coherent": "x-default présent"},
            explanation=f"{len(with_hreflang)} page(s) avec hreflang (score moyen {score}).",
            evidence=_EVIDENCE_HTML,
            weight=self.weight,
        )
