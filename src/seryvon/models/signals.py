# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Signal models collected by the crawler and the connectors.

Scoring rules (`Criterion.evaluate`) read ONLY these structures: this is the
boundary between collection (non-deterministic: network, time) and scoring
(deterministic). The same `SignalBundle` must always produce the same scores —
a property covered by an explicit test (document 03, §9).

`signal_schema_version` is bumped on every structural change
(2 = `aso` block; 3 = M3.1 signals OG/Twitter/hreflang/links/`site`;
4 = M3.2 GSO/AEO on-page signals + static ASO populated;
5 = agent-bot access in `site`; 6 = NLWeb status in `external`;
7 = M3.3 GEO on-page core signals + `audited_at`;
8 = aggregated LLM citation metrics in `external` (M4, Phase 3);
9 = GSC rank-tracking signals in `external` (M10)).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

SIGNAL_SCHEMA_VERSION = 9


class WebMcpSignals(BaseModel):
    """WebMCP signals extracted from the HTML/DOM (ASO pillar, adapted from audit_webmcp.py)."""

    has_register_tool: bool = False
    has_tool_attributes: bool = False
    tool_count: int = 0
    partial_signals: bool = False


class AsoSignals(BaseModel):
    """Block of static ASO signals (document 05, §2.4)."""

    webmcp: WebMcpSignals = Field(default_factory=WebMcpSignals)
    potential_actions: list[str] = Field(default_factory=list)
    action_schema_types: list[str] = Field(default_factory=list)
    agent_usable_forms: int = 0
    openapi_links: list[str] = Field(default_factory=list)


class PageSignals(BaseModel):
    """Internal signals of a page (HTML/DOM). Extended phase by phase.

    In Phase 0, only the base fields are populated (title, meta, headings,
    content metrics, raw structured data). The others keep their default values
    and are filled in during Phases 1–2.
    """

    url: str
    status_code: int | None = None
    render_mode: str | None = None  # "ssr" | "csr" (M2 heuristic, decision D2)
    redirects: int = 0  # number of redirect hops before the final URL

    title: str | None = None
    meta_description: str | None = None
    canonical: str | None = None
    meta_robots: str | None = None

    # Social metadata (full key -> content), e.g. {"og:title": "..."}.
    open_graph: dict[str, str] = Field(default_factory=dict)
    twitter_card: dict[str, str] = Field(default_factory=dict)
    # Declared hreflang: language code -> href (e.g. {"fr": "...", "x-default": "..."}).
    hreflang: dict[str, str] = Field(default_factory=dict)

    h1_count: int = 0
    headings: dict[str, int] = Field(default_factory=dict)  # {"h1": 1, "h2": 4, ...}

    word_count: int = 0
    text_ratio: float | None = None

    structured_data_types: list[str] = Field(default_factory=list)
    internal_links: int = 0
    external_links: int = 0
    # Absolute internal targets (same host), deduplicated and sorted: link graph
    # for the links.orphans criterion (populated by M3.1).
    internal_link_targets: list[str] = Field(default_factory=list)
    images_total: int = 0
    images_with_alt: int = 0

    # M3.2 on-page signals (GSO/AEO) — feed the GSO and AEO pillars.
    tables_count: int = 0  # <table> tables (itemlist / comparison)
    definition_lists_count: int = 0  # <dl> lists (glossaries / definitions)
    question_headings: int = 0  # Hn headings phrased as a question (Q&A format)
    lead_paragraph_words: int = 0  # words of the first paragraph (answer-directness)
    has_author: bool = False  # author/Person declared (JSON-LD)
    author_has_credentials: bool = False  # Person with credentials (jobTitle, sameAs…)
    has_structured_dates: bool = False  # datePublished / dateModified in JSON-LD

    # M3.3 on-page signals (GEO core) — feed the GEO pillar.
    main_text_ratio: float | None = None  # main content / total text (noise_ratio)
    entity_count: int = 0  # distinct entities estimated (heuristic, DG1)
    external_link_domains: list[str] = Field(default_factory=list)  # distinct outbound domains
    content_date: str | None = None  # most recent structured date (ISO 8601) for freshness
    social_platforms: list[str] = Field(default_factory=list)  # linked platforms (sameAs/social)

    aso: AsoSignals = Field(default_factory=AsoSignals)


class EngineCitationMetrics(BaseModel):
    """Per-engine breakdown of citation metrics (document 07 §9)."""

    citation_rate: float = 0.0  # 0–1: retrieval responses citing the domain
    mention_rate: float = 0.0  # 0–1: responses mentioning the brand
    citation_confidence: float = 0.0  # 0–1: consistency over K repetitions
    average_position: float | None = None  # average rank when cited


class CitationMetrics(BaseModel):
    """Aggregated LLM citation metrics (M4, document 07 §9).

    Deterministic output of the aggregator (`seryvon.citation.aggregate`) from the
    collected `LlmResponse` objects. `citation_rate` (*retrieval* mode) feeds both
    `geo.citation_rate` and `aeo.llm_citation`; `knowledge_presence` (mention in
    bare mode) is purely informational (no dedicated criterion, document 04).
    """

    citation_rate: float = 0.0  # 0–1: domain cited (retrieval)
    mention_rate: float = 0.0  # 0–1: brand mentioned (all modes)
    citation_confidence: float = 0.0  # 0–1: stability over K repetitions
    share_of_voice: float | None = None  # domain / (domain + competitors)
    knowledge_presence: float | None = None  # mention in bare mode (awareness), informational
    average_position: float | None = None
    per_engine: dict[str, EngineCitationMetrics] = Field(default_factory=dict)
    engines: list[str] = Field(default_factory=list)
    prompt_count: int = 0
    repetitions: int = 0
    prompt_set_version: int | None = None  # temporal traceability (document 08 §8)


class GscQuery(BaseModel):
    """A single GSC search analytics row (M10, document 07 §5)."""

    query: str
    position: float  # average_position (GSC doc — never instantaneous)
    clicks: int
    impressions: int
    ctr: float  # 0–1


class GscResult(BaseModel):
    """GSC search analytics snapshot for a domain (M10 Rank Tracking).

    Populated by `connectors.gsc.fetch_gsc`; empty (`queries=[]`,
    `avg_position=None`) when GSC is not configured or the property is not
    accessible. `avg_position=None` => dependent criteria `not_measured`.
    """

    queries: list[GscQuery] = Field(default_factory=list)
    total_clicks: int = 0
    total_impressions: int = 0
    avg_ctr: float = 0.0
    avg_position: float | None = None
    date_range_days: int = 90


class ExternalSignals(BaseModel):
    """Signals from external APIs (PSI, OpenPageRank, LLM, SERP, GSC...).

    All optional: a missing signal => `not_measured` criterion (never estimated,
    document 01, §6.2). Empty in Phase 0.
    """

    core_web_vitals: dict[str, float] | None = None
    lighthouse_performance: float | None = None
    open_page_rank: float | None = None
    referring_domains: int | None = None
    kg_presence: bool | None = None
    citation_metrics: CitationMetrics | None = None
    ai_overview_presence: float | None = None
    ai_discovery_endpoints: dict[str, bool] | None = None
    nlweb_status: str | None = None  # "conformant" / "present" / "absent"
    blocked_agent_bots: list[str] | None = None
    brand_coherence: dict[str, float] | None = None
    gsc_data: GscResult | None = None  # M10 rank tracking (GSC service account BYOK)


class SiteSignals(BaseModel):
    """Site-level signals from M1 Discovery (feed the crawl.* criteria)."""

    robots_found: bool = False
    crawl_delay: float | None = None
    sitemap_valid: bool = False  # at least one sitemap fetched and parsed
    sitemap_url_count: int = 0  # number of same-host URLs extracted from sitemaps
    # Agent-bot access (aso.agent_access) — derived from robots.txt by M1.
    blocked_agent_bots: list[str] = Field(default_factory=list)
    agent_bots_checked: int = 0  # number of agent bots tested (denominator)


class SignalBundle(BaseModel):
    """Complete aggregate of an audit's signals, consumed by the scoring engine."""

    domain: str
    signal_schema_version: int = SIGNAL_SCHEMA_VERSION
    # Frozen audit reference date: deterministic basis for geo.freshness (DG2).
    audited_at: datetime | None = None
    pages: list[PageSignals] = Field(default_factory=list)
    site: SiteSignals = Field(default_factory=SiteSignals)
    external: ExternalSignals = Field(default_factory=ExternalSignals)

    @property
    def home(self) -> PageSignals | None:
        """First crawled page (the home page)."""
        return self.pages[0] if self.pages else None
