# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""GEO pillar rules (Generative Engine Optimization), document 04 §3.

GEO on-page core (Phase 2.6): `geo.ssr` (render_mode heuristic, D10),
`noise_ratio`, `entity_density`, `primary_sources`, `authors`, `cross_platform`,
`freshness`. Freshness reads `SignalBundle.audited_at` (frozen reference, DG2 ->
determinism). LLM citation (Phase 3, M4): `geo.citation_rate`, `mention_rate`,
`citation_confidence` read `external.citation_metrics` (`not_measured` without a BYOK key).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from typing import ClassVar
from urllib.parse import urlsplit

from seryvon.i18n import t
from seryvon.models.criterion import Criterion, CriterionResult, ThresholdConfig, register
from seryvon.models.enums import Status, status_from_score
from seryvon.models.signals import PageSignals, SignalBundle

#: Max number of route families surfaced in `geo.ssr` raw_value (avoid huge payloads
#: on sites with many top-level sections; the largest CSR groups matter most).
_SSR_MAX_FAMILIES = 12
#: Max number of individual CSR pages surfaced as "top offenders" (worst content
#: parity first — least of the post-JS content already present in raw HTML).
_SSR_MAX_OFFENDERS = 10

# GEO on-page core thresholds (document 04 §3).
_NOISE_RATIO_TARGET = 0.20
_ENTITY_DENSITY_MIN = 0.02
_ENTITY_DENSITY_MAX = 0.20
_CROSS_PLATFORM_TARGET = 4
_FRESH_DAYS = 90
_STALE_DAYS = 365


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 2) if values else 0.0


def _route_family(url: str) -> str:
    """Group a URL under a top-level route section for the `geo.ssr` breakdown.

    Skips a leading 2-letter locale segment (e.g. `/en/models/x` -> "models")
    so per-locale variants of the same section aren't split into separate rows.
    """
    segments = [s for s in urlsplit(url).path.split("/") if s]
    if segments and len(segments[0]) == 2 and segments[0].isalpha() and len(segments) > 1:
        segments = segments[1:]
    return segments[0] if segments else "root"


def _ssr_breakdown_by_route(pages: list[PageSignals]) -> list[dict[str, int | str]]:
    """Per-route-family ssr/csr counts, sorted by CSR count (biggest gaps first)."""
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"ssr": 0, "csr": 0})
    for p in pages:
        if p.render_mode not in ("ssr", "csr"):
            continue
        counts[_route_family(p.url)][p.render_mode] += 1
    families = sorted(
        counts.items(), key=lambda item: (-item[1]["csr"], -(item[1]["ssr"] + item[1]["csr"]))
    )
    return [
        {"path": family, "pages": c["ssr"] + c["csr"], "ssr": c["ssr"], "csr": c["csr"]}
        for family, c in families[:_SSR_MAX_FAMILIES]
    ]


def _page_parity(page: PageSignals) -> float:
    """Fraction of the post-JS content already present in the raw HTML (0-1).

    Playwright pages carry both word counts -> continuous parity `raw / rendered`
    (capped at 1.0). Heuristic-fallback pages have no counts -> binary from
    `render_mode` (ssr = full parity, csr = none). This is the per-page signal
    averaged into the `geo.ssr` score: a page already largely present in raw HTML
    scores high even when JS later adds secondary blocks (nav, related listings).
    """
    raw, rendered = page.raw_word_count, page.rendered_word_count
    if raw is not None and rendered is not None:
        return 1.0 if rendered <= 0 else min(1.0, raw / rendered)
    return 1.0 if page.render_mode == "ssr" else 0.0


def _page_delta(page: PageSignals) -> int | None:
    """Words added by JS (rendered - raw), or None for heuristic-fallback pages."""
    if page.raw_word_count is None or page.rendered_word_count is None:
        return None
    return page.rendered_word_count - page.raw_word_count


def _ssr_csr_pages_ranked(pages: list[PageSignals]) -> list[PageSignals]:
    """CSR pages, worst content-parity first (thin static shells before rich pages).

    Ordering reflects urgency: a page with almost no static content ranks above a
    page already rich in raw HTML that merely gains secondary blocks via JS, even
    if the latter has a larger absolute word delta. Heuristic-fallback CSR pages
    (no counts) sort last, by URL, since their parity is unknown.
    """
    csr = [p for p in pages if p.render_mode == "csr"]
    ranked = sorted(
        (p for p in csr if _page_delta(p) is not None),
        key=lambda p: (_page_parity(p), -(_page_delta(p) or 0)),
    )
    unknown = sorted((p for p in csr if _page_delta(p) is None), key=lambda p: p.url)
    return ranked + unknown


def _page_offender_row(page: PageSignals) -> dict[str, int | str | None]:
    return {
        "url": page.url,
        "raw_words": page.raw_word_count,
        "rendered_words": page.rendered_word_count,
        "delta": _page_delta(page),
        "parity_pct": round(_page_parity(page) * 100),
    }


def _ssr_top_offenders(pages: list[PageSignals]) -> list[dict[str, int | str | None]]:
    """Worst-parity CSR pages for the `geo.ssr` hint panel (Playwright pages only)."""
    ranked = [p for p in _ssr_csr_pages_ranked(pages) if _page_delta(p) is not None]
    return [_page_offender_row(p) for p in ranked[:_SSR_MAX_OFFENDERS]]


def _ssr_affected_pages(pages: list[PageSignals]) -> list[str]:
    """All CSR page URLs, worst content-parity first — feeds the action-plan card's
    affected-pages list (chips + CSV export) via `evidence['non_conformes']`.
    """
    return [p.url for p in _ssr_csr_pages_ranked(pages)]


def _ssr_word_deltas(pages: list[PageSignals]) -> dict[str, dict[str, int]]:
    """Per-URL parity detail for every CSR page (uncapped, unlike `top_offenders`).

    Lets the frontend CSV export attach raw/rendered word counts, delta and parity
    to each affected page, not just the top 10 shown in the hint panel.
    """
    result: dict[str, dict[str, int]] = {}
    for p in _ssr_csr_pages_ranked(pages):
        delta = _page_delta(p)
        if delta is None or p.raw_word_count is None or p.rendered_word_count is None:
            continue
        result[p.url] = {
            "raw_words": p.raw_word_count,
            "rendered_words": p.rendered_word_count,
            "delta": delta,
            "parity_pct": round(_page_parity(p) * 100),
        }
    return result


def _parse_date(value: str) -> date | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        return None


@register
class GeoSsrCriterion(Criterion):
    """Content parity before JS (`geo.ssr`): how much page content a JS-free crawler sees.

    Per-page parity is `raw_words / rendered_words` (capped at 1.0); the score is
    the mean across pages. A page already rich in raw HTML scores high even when JS
    adds secondary blocks — only pages whose substance is JS-injected drag it down.
    The binary `render_mode` (ssr/csr) still labels each page and drives the
    diagnostic breakdown, but no longer decides the score on its own.
    """

    key = "geo.ssr"
    pillars: ClassVar[list[str]] = ["geo", "aeo", "aso"]
    weight = 1.8

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        pages_with_mode = [p for p in signals.pages if p.render_mode]
        if not pages_with_mode:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.render_mode_unavailable")
            )
        parities = [_page_parity(p) for p in pages_with_mode]
        mean_parity = sum(parities) / len(parities)
        score = round(mean_parity * 100, 2)
        ssr = sum(1 for p in pages_with_mode if p.render_mode == "ssr")
        csr = len(pages_with_mode) - ssr
        # Per-page detection method breakdown — a mix of Playwright DOM-diff and
        # heuristic (D2) fallback is common: individual renders can fail (timeout,
        # blocked page) and silently fall back per page (crawler/crawl.py).
        via_playwright = sum(1 for p in pages_with_mode if p.render_source == "playwright")
        via_heuristic = len(pages_with_mode) - via_playwright
        source = (
            "Playwright (DOM diff)"
            if via_heuristic == 0
            else "heuristic (D2)"
            if via_playwright == 0
            else f"mixed: {via_playwright} Playwright / {via_heuristic} heuristic"
        )
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={
                "pages": len(pages_with_mode),
                "mean_parity": round(mean_parity, 4),
                "ssr": ssr,
                "csr": csr,
                "detected_via_playwright": via_playwright,
                "detected_via_heuristic": via_heuristic,
                "by_route": _ssr_breakdown_by_route(pages_with_mode),
                "top_offenders": _ssr_top_offenders(pages_with_mode),
                "word_deltas": _ssr_word_deltas(pages_with_mode),
            },
            score=score,
            status=status_from_score(score),
            threshold={"target": "100% content parity before JS"},
            explanation=t(
                "expl.ssr", parity=round(score), csr=csr, total=len(pages_with_mode)
            ),
            evidence={"source": source, "non_conformes": _ssr_affected_pages(pages_with_mode)},
            weight=self.weight,
        )


@register
class GeoNoiseRatioCriterion(Criterion):
    """Content/noise ratio (`geo.noise_ratio`): >= 0.20 = optimal."""

    key = "geo.noise_ratio"
    pillars: ClassVar[list[str]] = ["geo"]
    weight = 0.8

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        ratios = [p.main_text_ratio for p in signals.pages if p.main_text_ratio is not None]
        if not ratios:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.noise_ratio_unavailable")
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
            explanation=t("expl.noise_ratio", pages=len(ratios)),
            evidence={"source": "HTML (contenu principal)"},
            weight=self.weight,
        )


@register
class GeoEntityDensityCriterion(Criterion):
    """Entity density (`geo.entity_density`): normalized over a target range (heuristic)."""

    key = "geo.entity_density"
    pillars: ClassVar[list[str]] = ["geo"]
    weight = 1.0

    def _score_page(self, entity_count: int, word_count: int) -> float:
        density = entity_count / word_count
        if density < _ENTITY_DENSITY_MIN:
            return round(density / _ENTITY_DENSITY_MIN * 100, 2)
        if density <= _ENTITY_DENSITY_MAX:
            return 100.0
        return 60.0  # too dense (likely noise/lists)

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        pages = [p for p in signals.pages if p.word_count > 0]
        if not pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_text_content")
            )
        score = _mean([self._score_page(p.entity_count, p.word_count) for p in pages])
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"pages": len(pages)},
            score=score,
            status=status_from_score(score),
            threshold={"min": _ENTITY_DENSITY_MIN, "max": _ENTITY_DENSITY_MAX},
            explanation=t("expl.entity_density", pages=len(pages)),
            evidence={"source": "heuristique entités (M3.3)"},
            weight=self.weight,
        )


@register
class GeoPrimarySourcesCriterion(Criterion):
    """Primary sources (`geo.primary_sources`): >=1 outbound link on content pages (aeo tag).

    Only counts pages with enough text to be considered content pages (word_count >=
    _CONTENT_MIN_WORDS). Lightweight listing/catalog pages are excluded — they are not
    expected to cite external sources. Threshold: 50 % OK / 20 % WARNING (lower than the
    global 80/50 because citing sources on every content page is a high bar).
    """

    key = "geo.primary_sources"
    pillars: ClassVar[list[str]] = ["geo", "aeo"]
    weight = 1.2

    # Pages below this word count are treated as structural/listing pages.
    _CONTENT_MIN_WORDS: ClassVar[int] = 300
    _OK_RATIO: ClassVar[float] = 0.50
    _WARN_RATIO: ClassVar[float] = 0.20

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        all_pages = signals.pages
        if not all_pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_pages")
            )
        th = (thresholds or {}).get(self.key, {})
        min_words = int(th.get("min_content_words", self._CONTENT_MIN_WORDS))
        ok_ratio = float(th.get("ok_ratio", self._OK_RATIO))
        warn_ratio = float(th.get("warn_ratio", self._WARN_RATIO))

        content_pages = [p for p in all_pages if p.word_count >= min_words]
        excluded = len(all_pages) - len(content_pages)

        if not content_pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_content_pages")
            )

        pages_with = [p.url for p in content_pages if p.external_link_domains]
        pages_without = [p.url for p in content_pages if not p.external_link_domains]
        with_sources = len(pages_with)
        ratio = with_sources / len(content_pages)
        score = round(ratio * 100, 2)

        if ratio >= ok_ratio:
            status = Status.OK
        elif ratio >= warn_ratio:
            status = Status.WARNING
        else:
            status = Status.CRITICAL

        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={
                "pages": len(all_pages),
                "content_pages": len(content_pages),
                "with_sources": with_sources,
                "excluded_structural": excluded,
            },
            score=score,
            status=status,
            threshold={
                "min_content_words": min_words,
                "ok_ratio": ok_ratio,
                "warn_ratio": warn_ratio,
            },
            explanation=t(
                "expl.primary_sources",
                without_sources=len(pages_without),
                total=len(content_pages),
                excluded=excluded,
            ),
            evidence={
                "source": "static HTML <a href>",
                "sample_with_sources": pages_with[:10],
                "non_conformes": pages_without[:30],
            },
            weight=self.weight,
        )


@register
class GeoAuthorsCriterion(Criterion):
    """Identifiable authors (`geo.authors`): presence of a structured author (aeo tag)."""

    key = "geo.authors"
    pillars: ClassVar[list[str]] = ["geo", "aeo"]
    weight = 1.2

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        pages = signals.pages
        if not pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_pages")
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
            explanation=t("expl.geo_authors_present") if present else t("expl.geo_authors_absent"),
            evidence={"source": "JSON-LD"},
            weight=self.weight,
        )


@register
class GeoCrossPlatformCriterion(Criterion):
    """Cross-platform presence (`geo.cross_platform`): >=4 platforms = 100 (aso tag)."""

    key = "geo.cross_platform"
    pillars: ClassVar[list[str]] = ["geo", "aso"]
    weight = 1.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        pages = signals.pages
        if not pages:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_pages")
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
            explanation=t(
                "expl.cross_platform",
                count=len(platforms),
                platforms=platforms if platforms else t("word.none"),
            ),
            evidence={"source": "sameAs + liens sociaux"},
            weight=self.weight,
        )


@register
class GeoFreshnessCriterion(Criterion):
    """Freshness (`geo.freshness`): content < 90 days = optimal (aeo tag).

    Age computed against `SignalBundle.audited_at` (frozen reference, DG2 determinism).
    """

    key = "geo.freshness"
    pillars: ClassVar[list[str]] = ["geo", "aeo"]
    weight = 1.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        if signals.audited_at is None:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_audit_reference")
            )
        dates = [d for p in signals.pages if p.content_date and (d := _parse_date(p.content_date))]
        if not dates:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.no_content_dates")
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
            explanation=t("expl.freshness", age=age),
            evidence={"source": "dates JSON-LD vs date d'audit"},
            weight=self.weight,
        )


# LLM citation criteria (M4, Phase 3): read the aggregated, deterministic metrics
# from `external.citation_metrics`. Without a BYOK key => `not_measured`.


@register
class GeoCitationRateCriterion(Criterion):
    """LLM citation rate (`geo.citation_rate`): % of retrieval responses citing the domain."""

    key = "geo.citation_rate"
    pillars: ClassVar[list[str]] = ["geo"]
    weight = 2.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        cm = signals.external.citation_metrics
        if cm is None:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.citation_unavailable")
            )
        score = round(cm.citation_rate * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"citation_rate": cm.citation_rate, "engines": cm.engines},
            score=score,
            status=status_from_score(score),
            threshold={"formula": "% réponses retrieval citant le domaine"},
            explanation=t(
                "expl.citation_rate",
                score=score,
                prompts=cm.prompt_count,
                reps=cm.repetitions,
                engines=len(cm.engines),
            ),
            evidence={"source": "M4 citation tracking", "average_position": cm.average_position},
            weight=self.weight,
        )


@register
class GeoMentionRateCriterion(Criterion):
    """LLM mention rate (`geo.mention_rate`): % of responses mentioning the brand."""

    key = "geo.mention_rate"
    pillars: ClassVar[list[str]] = ["geo"]
    weight = 1.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        cm = signals.external.citation_metrics
        if cm is None:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.citation_unavailable")
            )
        score = round(cm.mention_rate * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={
                "mention_rate": cm.mention_rate,
                "knowledge_presence": cm.knowledge_presence,
            },
            score=score,
            status=status_from_score(score),
            threshold={"formula": "% réponses mentionnant la marque"},
            explanation=t("expl.mention_rate", score=score),
            evidence={"source": "M4 citation tracking"},
            weight=self.weight,
        )


@register
class GeoCitationConfidenceCriterion(Criterion):
    """Citation stability (`geo.citation_confidence`): consistency over K repetitions."""

    key = "geo.citation_confidence"
    pillars: ClassVar[list[str]] = ["geo"]
    weight = 0.8

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        cm = signals.external.citation_metrics
        if cm is None:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.citation_unavailable")
            )
        score = round(cm.citation_confidence * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={
                "citation_confidence": cm.citation_confidence,
                "repetitions": cm.repetitions,
            },
            score=score,
            status=status_from_score(score),
            threshold={"formula": "constance de citation sur K répétitions"},
            explanation=t("expl.citation_confidence", score=score, reps=cm.repetitions),
            evidence={"source": "M4 citation tracking"},
            weight=self.weight,
        )


@register
class GeoKnowledgePresenceCriterion(Criterion):
    """Brand knowledge presence (`geo.knowledge_presence`).

    Fraction of knowledge-mode LLM responses that mention the domain.
    """

    key = "geo.knowledge_presence"
    pillars: ClassVar[list[str]] = ["geo"]
    weight = 0.8

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        cm = signals.external.citation_metrics
        if cm is None or cm.knowledge_presence is None:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.citation_unavailable")
            )
        score = round(cm.knowledge_presence * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"knowledge_presence": cm.knowledge_presence, "engines": cm.engines},
            score=score,
            status=status_from_score(score),
            threshold={"formula": "% réponses knowledge citant la marque"},
            explanation=t("expl.knowledge_presence", score=score),
            evidence={"source": "M4 citation tracking (knowledge mode)"},
            weight=self.weight,
        )


@register
class GeoShareOfVoiceCriterion(Criterion):
    """Citation share of voice (`geo.share_of_voice`): domain citations / (domain + competitors).

    `not_measured` unless competitors were declared when running citation tracking.
    """

    key = "geo.share_of_voice"
    pillars: ClassVar[list[str]] = ["geo"]
    weight = 1.0

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        cm = signals.external.citation_metrics
        if cm is None or cm.share_of_voice is None:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.sov_no_competitors")
            )
        score = round(cm.share_of_voice * 100, 2)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"share_of_voice": cm.share_of_voice},
            score=score,
            status=status_from_score(score),
            threshold={"formula": "citations domaine / (domaine + concurrents)"},
            explanation=t("expl.share_of_voice", score=score),
            evidence={"source": "M4 citation tracking"},
            weight=self.weight,
        )


# Scoring function for average citation position: position 1 → 100, each step -20, floor 0.
def _position_score(avg_pos: float) -> float:
    return round(max(0.0, 100.0 - (avg_pos - 1.0) * 20.0), 2)


@register
class GeoCitationPositionCriterion(Criterion):
    """Average citation position (`geo.citation_position`).

    Mean rank when the domain is cited by LLMs (lower is better).
    """

    key = "geo.citation_position"
    pillars: ClassVar[list[str]] = ["geo"]
    weight = 0.8

    def evaluate(
        self, signals: SignalBundle, thresholds: ThresholdConfig | None = None
    ) -> CriterionResult:
        cm = signals.external.citation_metrics
        if cm is None or cm.average_position is None:
            return CriterionResult.not_measured(
                self.key, self.pillars, self.weight, t("reason.citation_unavailable")
            )
        score = _position_score(cm.average_position)
        return CriterionResult(
            key=self.key,
            pillars=self.pillars,
            raw_value={"average_position": cm.average_position},
            score=score,
            status=status_from_score(score),
            threshold={"formula": "position 1 = 100 ; −20 par rang ; plancher 0"},
            explanation=t("expl.citation_position", position=cm.average_position, score=score),
            evidence={"source": "M4 citation tracking"},
            weight=self.weight,
        )
