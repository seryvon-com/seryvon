# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Modèles de signaux collectés par le crawler et les connecteurs.

Les règles de scoring (`Criterion.evaluate`) ne lisent QUE ces structures :
c'est la frontière entre la collecte (non déterministe : réseau, temps) et le
scoring (déterministe). Un même `SignalBundle` doit toujours produire les mêmes
scores — propriété testée explicitement (document 03, §9).

Le `signal_schema_version` est incrémenté à chaque évolution de structure
(le bloc `aso` l'a fait passer à 2 ; les signaux M3.1 — Open Graph, Twitter,
hreflang, cibles de liens, bloc `site` — l'ont fait passer à 3).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

SIGNAL_SCHEMA_VERSION = 3


class WebMcpSignals(BaseModel):
    """Signaux WebMCP extraits du HTML/DOM (pilier ASO, transposé de audit_webmcp.py)."""

    has_register_tool: bool = False
    has_tool_attributes: bool = False
    tool_count: int = 0
    partial_signals: bool = False


class AsoSignals(BaseModel):
    """Bloc de signaux ASO statiques (document 05, §2.4)."""

    webmcp: WebMcpSignals = Field(default_factory=WebMcpSignals)
    potential_actions: list[str] = Field(default_factory=list)
    action_schema_types: list[str] = Field(default_factory=list)
    agent_usable_forms: int = 0
    openapi_links: list[str] = Field(default_factory=list)


class PageSignals(BaseModel):
    """Signaux internes d'une page (HTML/DOM). Étendu progressivement par phase.

    En Phase 0, seuls les champs de base sont peuplés (title, meta, headings,
    métriques de contenu, données structurées brutes). Les autres restent à
    leurs valeurs par défaut et seront alimentés en Phases 1–2.
    """

    url: str
    status_code: int | None = None
    render_mode: str | None = None  # "ssr" | "csr" (heuristique M2, décision D2)
    redirects: int = 0  # nombre de sauts de redirection avant l'URL finale

    title: str | None = None
    meta_description: str | None = None
    canonical: str | None = None
    meta_robots: str | None = None

    # Métadonnées sociales (clé complète -> contenu), ex. {"og:title": "..."}.
    open_graph: dict[str, str] = Field(default_factory=dict)
    twitter_card: dict[str, str] = Field(default_factory=dict)
    # hreflang déclarés : code de langue -> href (ex. {"fr": "...", "x-default": "..."}).
    hreflang: dict[str, str] = Field(default_factory=dict)

    h1_count: int = 0
    headings: dict[str, int] = Field(default_factory=dict)  # {"h1": 1, "h2": 4, ...}

    word_count: int = 0
    text_ratio: float | None = None

    structured_data_types: list[str] = Field(default_factory=list)
    internal_links: int = 0
    external_links: int = 0
    # Cibles internes absolues (même hôte), dédupliquées et triées : graphe de
    # maillage pour le critère links.orphans (renseigné par M3.1).
    internal_link_targets: list[str] = Field(default_factory=list)
    images_total: int = 0
    images_with_alt: int = 0

    aso: AsoSignals = Field(default_factory=AsoSignals)


class ExternalSignals(BaseModel):
    """Signaux issus d'APIs externes (PSI, OpenPageRank, LLM, SERP, GSC...).

    Tous optionnels : un signal absent => critère `not_measured` (jamais estimé,
    document 01, §6.2). Vide en Phase 0.
    """

    core_web_vitals: dict[str, float] | None = None
    lighthouse_performance: float | None = None
    open_page_rank: float | None = None
    referring_domains: int | None = None
    kg_presence: bool | None = None
    llm_citations: dict[str, float] | None = None
    ai_overview_presence: float | None = None
    ai_discovery_endpoints: dict[str, bool] | None = None
    blocked_agent_bots: list[str] | None = None
    brand_coherence: dict[str, float] | None = None


class SiteSignals(BaseModel):
    """Signaux au niveau site, issus de M1 Discovery (alimente les critères crawl.*)."""

    robots_found: bool = False
    crawl_delay: float | None = None
    sitemap_valid: bool = False  # au moins un sitemap récupéré et parsé
    sitemap_url_count: int = 0  # nombre d'URLs same-host extraites des sitemaps


class SignalBundle(BaseModel):
    """Agrégat complet des signaux d'un audit, consommé par le moteur de scoring."""

    domain: str
    signal_schema_version: int = SIGNAL_SCHEMA_VERSION
    pages: list[PageSignals] = Field(default_factory=list)
    site: SiteSignals = Field(default_factory=SiteSignals)
    external: ExternalSignals = Field(default_factory=ExternalSignals)

    @property
    def home(self) -> PageSignals | None:
        """Première page crawlée (la home)."""
        return self.pages[0] if self.pages else None
