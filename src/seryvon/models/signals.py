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
(2 = bloc `aso` ; 3 = signaux M3.1 OG/Twitter/hreflang/liens/`site` ;
4 = signaux M3.2 GSO/AEO on-page + ASO statique peuplé ;
5 = accès des bots d'agents dans `site` ; 6 = statut NLWeb dans `external` ;
7 = signaux M3.3 cœur GEO on-page + `audited_at` ;
8 = métriques de citation LLM agrégées dans `external` (M4, Phase 3)).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

SIGNAL_SCHEMA_VERSION = 8


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

    # Signaux on-page M3.2 (GSO/AEO) — alimentent les piliers GSO et AEO.
    tables_count: int = 0  # tableaux <table> (itemlist / comparatifs)
    definition_lists_count: int = 0  # listes <dl> (glossaires / definitions)
    question_headings: int = 0  # titres Hn formulés en question (format Q-R)
    lead_paragraph_words: int = 0  # mots du 1er paragraphe (answer-directness)
    has_author: bool = False  # auteur/Person déclaré (JSON-LD)
    author_has_credentials: bool = False  # Person avec credentials (jobTitle, sameAs…)
    has_structured_dates: bool = False  # datePublished / dateModified en JSON-LD

    # Signaux on-page M3.3 (cœur GEO) — alimentent le pilier GEO.
    main_text_ratio: float | None = None  # contenu principal / texte total (noise_ratio)
    entity_count: int = 0  # entités distinctes estimées (heuristique, DG1)
    external_link_domains: list[str] = Field(default_factory=list)  # domaines sortants distincts
    content_date: str | None = None  # date structurée la plus récente (ISO 8601) pour freshness
    social_platforms: list[str] = Field(default_factory=list)  # plateformes liées (sameAs/sociaux)

    aso: AsoSignals = Field(default_factory=AsoSignals)


class EngineCitationMetrics(BaseModel):
    """Métriques de citation ventilées pour un moteur (document 07 §9)."""

    citation_rate: float = 0.0  # 0–1 : réponses retrieval citant le domaine
    mention_rate: float = 0.0  # 0–1 : réponses mentionnant la marque
    citation_confidence: float = 0.0  # 0–1 : constance sur K répétitions
    average_position: float | None = None  # rang moyen quand cité


class CitationMetrics(BaseModel):
    """Métriques de citation LLM agrégées (M4, document 07 §9).

    Produit déterministe de l'agrégateur (`seryvon.citation.aggregate`) à partir
    des `LlmResponse` collectées. `citation_rate` (mode *retrieval*) alimente
    `geo.citation_rate` ET `aeo.llm_citation` ; `knowledge_presence` (mention en
    mode nu) est purement informatif (pas de critère dédié, document 04).
    """

    citation_rate: float = 0.0  # 0–1 : domaine cité (retrieval)
    mention_rate: float = 0.0  # 0–1 : marque mentionnée (tous modes)
    citation_confidence: float = 0.0  # 0–1 : stabilité sur K répétitions
    share_of_voice: float | None = None  # domaine / (domaine + concurrents)
    knowledge_presence: float | None = None  # mention en mode nu (notoriété), informatif
    average_position: float | None = None
    per_engine: dict[str, EngineCitationMetrics] = Field(default_factory=dict)
    engines: list[str] = Field(default_factory=list)
    prompt_count: int = 0
    repetitions: int = 0
    prompt_set_version: int | None = None  # traçabilité temporelle (document 08 §8)


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
    citation_metrics: CitationMetrics | None = None
    ai_overview_presence: float | None = None
    ai_discovery_endpoints: dict[str, bool] | None = None
    nlweb_status: str | None = None  # "conformant" / "present" / "absent"
    blocked_agent_bots: list[str] | None = None
    brand_coherence: dict[str, float] | None = None


class SiteSignals(BaseModel):
    """Signaux au niveau site, issus de M1 Discovery (alimente les critères crawl.*)."""

    robots_found: bool = False
    crawl_delay: float | None = None
    sitemap_valid: bool = False  # au moins un sitemap récupéré et parsé
    sitemap_url_count: int = 0  # nombre d'URLs same-host extraites des sitemaps
    # Accès des bots d'agents (aso.agent_access) — dérivé de robots.txt par M1.
    blocked_agent_bots: list[str] = Field(default_factory=list)
    agent_bots_checked: int = 0  # nombre de bots d'agents testés (dénominateur)


class SignalBundle(BaseModel):
    """Agrégat complet des signaux d'un audit, consommé par le moteur de scoring."""

    domain: str
    signal_schema_version: int = SIGNAL_SCHEMA_VERSION
    # Date de référence de l'audit (figée) : base déterministe de geo.freshness (DG2).
    audited_at: datetime | None = None
    pages: list[PageSignals] = Field(default_factory=list)
    site: SiteSignals = Field(default_factory=SiteSignals)
    external: ExternalSignals = Field(default_factory=ExternalSignals)

    @property
    def home(self) -> PageSignals | None:
        """Première page crawlée (la home)."""
        return self.pages[0] if self.pages else None
