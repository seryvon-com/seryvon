# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Catalog of SEO pillar scoring rules (document 04, §2).

Multi-page aggregation:
- *page-level* criteria (title, description, h1, schema…): score = mean of the
  per-page scores (`PageCriterion`); `not_measured` if no page was crawled;
- *site-level* criteria (title uniqueness, orphans, indexability, HTTPS,
  sitemap, alt): computed directly over the whole crawl.

Determinism: `evaluate(signals, thresholds)` reads only the `SignalBundle` and
the thresholds (no I/O); outputs (evidence lists) are sorted. Overridable
thresholds flow through `thresholds` (e.g. `content.depth.target_words`).

`struct.schema` carries the multi-pillar tags gso/aeo/aso (Phase 2); the `perf.*`
rules (module `perf.py`) carry seo + gso.
"""

from __future__ import annotations

from collections.abc import Callable
from itertools import pairwise
from typing import Any, ClassVar

from seryvon.i18n import t
from seryvon.models.criterion import Criterion, CriterionResult, ThresholdConfig, register
from seryvon.models.enums import STATUS_OK_THRESHOLD, Status, status_from_score
from seryvon.models.signals import PageSignals, SignalBundle

# Default thresholds (document 04, §2).
TITLE_MIN_LEN, TITLE_MAX_LEN = 30, 60
DESC_MIN_LEN, DESC_MAX_LEN = 120, 158
CONTENT_MIN_WORDS = 800
TEXT_RATIO_MIN = 0.15
# Absolute number of missing-alt images above which img.alt cannot score `ok`.
# A percentage score is scale-invariant: 86% is 86% whether 1/7 or 102/738 images
# are missing. This floor keeps the score continuous but caps the status at
# `warning` so a large absolute backlog surfaces in the action plan.
IMG_ALT_MAX_MISSING = 25
LINKS_MIN, LINKS_MAX = 3, 100
MAX_REDIRECT_HOPS = 1
OG_REQUIRED = ("og:title", "og:description", "og:image", "og:url", "og:type")
TWITTER_FIELDS = ("twitter:card", "twitter:title", "twitter:description", "twitter:image")

_EVIDENCE_HTML: dict[str, Any] = {"source": "HTML parsing"}
_MAX_EVIDENCE = 10  # nombre max d'URLs listées en évidence


def _mean(values: list[float]) -> float:
    """Rounded mean of a list of scores (0.0 if empty)."""
    return round(sum(values) / len(values), 2) if values else 0.0


def _is_indexable(meta_robots: str | None) -> bool:
    """Indexable if no `noindex` directive is present."""
    return meta_robots is None or "noindex" not in meta_robots.lower()


# --------------------------------------------------------------------------- #
# Page-level criteria base                                                     #
# --------------------------------------------------------------------------- #
class PageCriterion(Criterion):
    """Criterion evaluated per page; audit score = mean of the per-page scores.

    Subclass and implement `score_page` (formula from document 04).
    `not_measured` if no page was crawled.
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
        """Mean of the per-page scores + evidence of the non-conformant pages."""
        pages = signals.pages
        if not pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_pages")
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
            explanation=t(
                "expl.page_conformance", failing=len(failing), total=len(pages), score=score
            ),
            evidence={**_EVIDENCE_HTML, "non_conformes": failing[:_MAX_EVIDENCE]},
            weight=self.weight,
        )

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        return self._aggregate(signals, self.score_page)


# --------------------------------------------------------------------------- #
# Metadata                                                                     #
# --------------------------------------------------------------------------- #
@register
class MetaTitleCriterion(PageCriterion):
    """Presence and length of the <title> tag (`meta.title`)."""

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
    """Presence and length of the meta description (`meta.description`)."""

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
    """Presence and validity of the canonical tag (`meta.canonical`)."""

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
    """Meta robots directive: is the page indexable (`meta.robots`)?"""

    key = "meta.robots"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.0
    label = "Meta robots"
    threshold: ClassVar[dict[str, Any]] = {"indexable": "pas de noindex"}

    def score_page(self, page: PageSignals) -> float:
        return 100.0 if _is_indexable(page.meta_robots) else 0.0


@register
class MetaTitleUniqueCriterion(Criterion):
    """Title uniqueness across all pages (`meta.title_unique`)."""

    key = "meta.title_unique"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        titles = [p.title for p in signals.pages if p.title]
        if not titles:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_titles")
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
            explanation=t("expl.title_unique", unique=unique, total=len(titles)),
            evidence=_EVIDENCE_HTML,
            weight=self.weight,
        )


# --------------------------------------------------------------------------- #
# Social metadata                                                              #
# --------------------------------------------------------------------------- #
@register
class OpenGraphCriterion(PageCriterion):
    """Completeness of the Open Graph tags (`og.complete`)."""

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
    """Presence of the Twitter Cards (`twitter.cards`)."""

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
# Semantic structure                                                           #
# --------------------------------------------------------------------------- #
@register
class StructH1Criterion(PageCriterion):
    """H1 uniqueness (`struct.h1`): exactly one per page."""

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
    """Heading hierarchy coherence (`struct.hierarchy`).

    Coherent = exactly one H1 and no skipped level (h2 -> h4 forbidden).
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
# Content                                                                      #
# --------------------------------------------------------------------------- #
@register
class ContentDepthCriterion(PageCriterion):
    """Content depth (`content.depth`): >= 800 words = optimal."""

    key = "content.depth"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.3
    label = "Profondeur de contenu"
    threshold: ClassVar[dict[str, Any]] = {"min_words": CONTENT_MIN_WORDS}

    @staticmethod
    def _target_words(thresholds: ThresholdConfig | None) -> float:
        """Word threshold: `content.depth.target_words` override or default 800."""
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
    """Text/code ratio (`content.text_ratio`): >= 0.15 = optimal."""

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
    """Presence of JSON-LD structured data (`struct.schema`).

    Multi-pillar: structured data is the foundation that SEO, GSO, AEO and agents
    (ASO) all consume.
    """

    key = "struct.schema"
    pillars: ClassVar[list[str]] = ["seo", "gso", "aeo", "aso"]
    weight = 1.5
    label = "Données structurées"
    threshold: ClassVar[dict[str, Any]] = {"min_types": 1}

    def score_page(self, page: PageSignals) -> float:
        return 100.0 if page.structured_data_types else 0.0


# --------------------------------------------------------------------------- #
# Internal linking                                                             #
# --------------------------------------------------------------------------- #
@register
class LinksInternalCriterion(PageCriterion):
    """Internal link volume per page (`links.internal`): 3 to 100."""

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
        return 60.0  # too few (< 3) or too many (> 100)


@register
class LinksOrphansCriterion(Criterion):
    """Orphan pages (`links.orphans`): without an inbound internal link.

    `not_measured` if fewer than two pages (no link graph to evaluate). The home
    (first page) is never considered an orphan.
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
                self.key, self.pillars, self.weight, t("reason.link_graph")
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
            explanation=t("expl.orphans", orphans=len(orphans), total=len(non_home)),
            evidence={**_EVIDENCE_HTML, "orphelines": orphans[:_MAX_EVIDENCE]},
            weight=self.weight,
        )


# --------------------------------------------------------------------------- #
# Technical accessibility                                                      #
# --------------------------------------------------------------------------- #
@register
class ImgAltCriterion(Criterion):
    """Alt-attribute coverage (`img.alt`): % of images with alt.

    `not_measured` if the site contains no image.
    """

    key = "img.alt"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 0.5

    @staticmethod
    def _max_missing(thresholds: ThresholdConfig | None) -> int:
        """Volume floor: `img.alt.max_missing` override or default `IMG_ALT_MAX_MISSING`."""
        section = thresholds.get("img.alt") if thresholds else None
        value = section.get("max_missing") if section else None
        if isinstance(value, int | float) and value > 0:
            return int(value)
        return IMG_ALT_MAX_MISSING

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        total = sum(p.images_total for p in signals.pages)
        if total == 0:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_images")
            )
        with_alt = sum(p.images_with_alt for p in signals.pages)
        without_alt = total - with_alt
        score = round(with_alt / total * 100, 2)
        status = status_from_score(score)
        # Volume floor: a passing percentage on a large image set can still hide a
        # significant absolute backlog. Cap the status at `warning` so it surfaces
        # in the action plan; the score itself stays continuous.
        max_missing = self._max_missing(thresholds)
        if status is Status.OK and without_alt >= max_missing:
            status = Status.WARNING
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={
                "images": total,
                "with_alt": with_alt,
                "without_alt": without_alt,
                "max_missing": max_missing,
            },
            score=score,
            status=status,
            threshold={"target": "100% d'images avec alt", "max_missing": max_missing},
            explanation=t("expl.img_alt", without_alt=without_alt, total=total),
            evidence=_EVIDENCE_HTML,
            weight=self.weight,
        )


@register
class ImgSvgAltCriterion(Criterion):
    """Inline SVG accessible names (`img.svg_alt`): % of content <svg> with a name.

    Complements `img.alt`: SVG-heavy sites (icon/illustration systems built on
    inline <svg> rather than <img>) can pass `img.alt` on a near-empty <img>
    count while their real visual content has no accessible name at all.
    Excludes decorative/hidden svgs (aria-hidden, role=presentation,
    display:none sprite sheets) and icons with a labeled context within a few
    ancestor levels (e.g. `<button>Learn <svg/></button>`, or `<time>Updated
    Mar 10<svg/></time>` — the icon is redundant with nearby visible text or
    an aria-label, so it needs no name of its own). A <title> child must have
    non-empty text to count as a name (an empty stub, as some charting
    libraries emit by default, does not).
    See `crawler.extract._svg_accessibility`. `not_measured` if the site has
    no such content <svg>.
    """

    key = "img.svg_alt"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 0.4

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        total = sum(p.svg_total for p in signals.pages)
        if total == 0:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_svg")
            )
        accessible = sum(p.svg_accessible for p in signals.pages)
        score = round(accessible / total * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={
                "svg": total,
                "accessible": accessible,
                "without_name": total - accessible,
            },
            score=score,
            status=status_from_score(score),
            threshold={"target": "100% des <svg> de contenu avec un nom accessible"},
            explanation=t("expl.img_svg_alt", without_name=total - accessible, total=total),
            evidence=_EVIDENCE_HTML,
            weight=self.weight,
        )


# --------------------------------------------------------------------------- #
# Crawl & indexability                                                         #
# --------------------------------------------------------------------------- #
@register
class CrawlIndexableCriterion(Criterion):
    """Indexability (`crawl.indexable`): % of pages that are HTTP 200 and not noindex."""

    key = "crawl.indexable"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.2

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        pages = signals.pages
        if not pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_pages")
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
            explanation=t("expl.indexable", non_indexable=len(pages) - indexable, total=len(pages)),
            evidence=_EVIDENCE_HTML,
            weight=self.weight,
        )


@register
class CrawlSitemapCriterion(Criterion):
    """Presence and validity of a sitemap (`crawl.sitemap`)."""

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
                t("expl.sitemap_valid", count=signals.site.sitemap_url_count)
                if valid
                else t("expl.sitemap_invalid")
            ),
            evidence={"source": "M1 Discovery"},
            weight=self.weight,
        )


@register
class CrawlHttpsCriterion(Criterion):
    """HTTPS security (`crawl.https`): % of pages served over HTTPS."""

    key = "crawl.https"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        pages = signals.pages
        if not pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_pages")
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
            explanation=t("expl.https", non_https=len(pages) - https, total=len(pages)),
            evidence=_EVIDENCE_HTML,
            weight=self.weight,
        )


@register
class CrawlRedirectsCriterion(PageCriterion):
    """Redirect chains (`crawl.redirects`): <= 1 hop = optimal."""

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
# GSC Rank Tracking (M10)                                                      #
# --------------------------------------------------------------------------- #
@register
class SeoAvgPositionCriterion(Criterion):
    """Average keyword position (`seo.avg_position`) from Google Search Console.

    `not_measured` when GSC is not configured (`gsc_data` absent or has no
    queries). Position thresholds follow the classic SEO CTR curve.
    The `raw_value` carries the full query list so the Rank Tracking UI can
    render the table without an extra API call.
    """

    key = "seo.avg_position"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 2.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        gsc = signals.external.gsc_data
        if gsc is None or gsc.avg_position is None:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.gsc_not_configured")
            )
        pos = gsc.avg_position
        if pos <= 3:
            score = 100.0
        elif pos <= 10:
            score = 75.0
        elif pos <= 20:
            score = 50.0
        else:
            score = 25.0
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={
                "avg_position": pos,
                "total_clicks": gsc.total_clicks,
                "total_impressions": gsc.total_impressions,
                "avg_ctr": gsc.avg_ctr,
                "date_range_days": gsc.date_range_days,
                "queries": [
                    {
                        "query": q.query,
                        "position": q.position,
                        "clicks": q.clicks,
                        "impressions": q.impressions,
                        "ctr": q.ctr,
                    }
                    for q in gsc.queries
                ],
                "pages": [
                    {
                        "page": p.page,
                        "position": p.position,
                        "clicks": p.clicks,
                        "impressions": p.impressions,
                        "ctr": p.ctr,
                    }
                    for p in gsc.pages
                ],
                "comparison": (gsc.comparison.model_dump() if gsc.comparison is not None else None),
            },
            score=score,
            status=status_from_score(score),
            threshold={"target": "average_position ≤ 10"},
            explanation=t(
                "expl.seo_avg_position",
                position=pos,
                queries=len(gsc.queries),
                days=gsc.date_range_days,
            ),
            evidence={"source": "Google Search Console API"},
            weight=self.weight,
        )


@register
class SeoClickThroughRateCriterion(Criterion):
    """Organic click-through rate (`seo.click_through_rate`) from GSC.

    `not_measured` when GSC is not configured or has no impressions.
    """

    key = "seo.click_through_rate"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 1.5

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        gsc = signals.external.gsc_data
        if gsc is None or gsc.total_impressions == 0:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.gsc_not_configured")
            )
        ctr_pct = round(gsc.avg_ctr * 100, 2)
        if ctr_pct >= 5.0:
            score = 100.0
        elif ctr_pct >= 2.0:
            score = 75.0
        elif ctr_pct >= 0.5:
            score = 50.0
        else:
            score = 25.0
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={
                "avg_ctr": gsc.avg_ctr,
                "total_clicks": gsc.total_clicks,
                "total_impressions": gsc.total_impressions,
            },
            score=score,
            status=status_from_score(score),
            threshold={"target": "CTR ≥ 5%"},
            explanation=t(
                "expl.seo_ctr",
                ctr=ctr_pct,
                clicks=gsc.total_clicks,
                impressions=gsc.total_impressions,
            ),
            evidence={"source": "Google Search Console API"},
            weight=self.weight,
        )


# --------------------------------------------------------------------------- #
# Internationalization                                                         #
# --------------------------------------------------------------------------- #
@register
class HreflangCriterion(Criterion):
    """hreflang coherence (`i18n.hreflang`).

    `not_measured` if no hreflang is declared (assumed monolingual site, validated
    decision). Otherwise: coherent if `x-default` is present.
    """

    key = "i18n.hreflang"
    pillars: ClassVar[list[str]] = ["seo"]
    weight = 0.5

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        with_hreflang = [p for p in signals.pages if p.hreflang]
        if not with_hreflang:
            return CriterionResult.not_applicable(
                self.key,
                self.pillars,
                self.weight,
                t("reason.no_hreflang"),
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
            explanation=t("expl.hreflang", count=len(with_hreflang), score=score),
            evidence=_EVIDENCE_HTML,
            weight=self.weight,
        )
