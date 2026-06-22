# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Message catalog: English (base) + French. Keys are dotted (e.g. `rec.meta.title`).

Add a key to BOTH locales. Templates use `str.format` named fields. Keep
produced text concise (it surfaces in reports, the dashboard and the CLI).
"""

from __future__ import annotations

# --------------------------------------------------------------------------- #
# Recommendations — one concise fix per criterion (document 04 §7-8).          #
# --------------------------------------------------------------------------- #
_REC_EN: dict[str, str] = {
    "meta.title": "Add a unique 30–60 character <title> on every page.",
    "meta.description": "Write a 120–158 character meta description.",
    "meta.canonical": "Declare an absolute canonical URL.",
    "meta.robots": "Remove noindex directives from pages meant to be indexed.",
    "meta.title_unique": "Deduplicate identical title tags.",
    "og.complete": "Complete the Open Graph tags (title, description, image, url, type).",
    "twitter.cards": "Add Twitter Cards (card, title, description, image).",
    "struct.h1": "Use a single H1 per page.",
    "struct.hierarchy": "Fix the heading hierarchy (one H1, no skipped level).",
    "struct.schema": "Add relevant JSON-LD structured data.",
    "content.depth": "Enrich the content (aim for ≥ 800 useful words).",
    "content.text_ratio": "Increase the text-to-code ratio (lighten the markup).",
    "links.internal": "Add 3 to 100 relevant internal links per page.",
    "links.orphans": "Link orphan pages from the navigation.",
    "img.alt": "Set the alt attribute on every image.",
    "crawl.indexable": "Fix non-indexable pages (HTTP status, noindex).",
    "crawl.sitemap": "Publish a valid sitemap.xml.",
    "crawl.https": "Serve every page over HTTPS.",
    "crawl.redirects": "Reduce redirect chains to one hop at most.",
    "i18n.hreflang": "Declare consistent hreflang with x-default.",
    "perf.lcp": "Optimize LCP (≤ 2500 ms).",
    "perf.cls": "Reduce CLS (≤ 0.1).",
    "perf.inp": "Improve INP (≤ 200 ms).",
    "perf.lighthouse": "Optimize performance (Lighthouse score).",
    "authority.opr": "Acquire quality backlinks and mentions.",
    "authority.backlinks": "Grow a profile of referring domains.",
    "gso.faqpage": "Add FAQPage schema on question pages.",
    "gso.howto": "Add HowTo schema on tutorials.",
    "gso.breadcrumb": "Add a BreadcrumbList to the template.",
    "gso.itemlist": "Structure lists with ItemList or tables.",
    "gso.qa_format": "Phrase extractable question-answer sections.",
    "gso.cwv_eligible": "Bring all 3 Core Web Vitals within thresholds.",
    "aeo.author_credentials": "Declare authors with credentials (Person).",
    "aeo.about_page": "Publish a detailed About page.",
    "aeo.defined_terms": "Add definitions (DefinedTerm or a glossary).",
    "aeo.dates_structured": "Expose datePublished/dateModified in JSON-LD.",
    "aeo.comparison_tables": "Add comparison tables.",
    "aeo.answer_directness": "Place a direct answer at the top of the page.",
    "aeo.kg_presence": "Create or strengthen the entity in Wikidata/Wikipedia.",
    "geo.ssr": "Serve content with server-side rendering (SSR).",
    "geo.noise_ratio": "Increase the share of useful content vs nav/boilerplate.",
    "geo.entity_density": "Densify the content with relevant named entities.",
    "geo.primary_sources": "Cite primary external sources (outbound links).",
    "geo.authors": "Declare a structured author (author/Person in JSON-LD).",
    "geo.cross_platform": "Reference the brand on ≥4 platforms (sameAs).",
    "geo.freshness": "Update the content and expose dateModified.",
    "geo.citation_rate": "Earn generative citations (citable reference content).",
    "geo.mention_rate": "Strengthen brand awareness (mentions, editorial presence).",
    "geo.citation_confidence": "Stabilize citation (consistent canonical content, authority).",
    "aeo.llm_citation": "Optimize for answer engines (direct answers, reliable sources).",
    "aso.mcp_readiness": "Expose a WebMCP server (registerTool / toolname).",
    "aso.potential_actions": "Add executable potentialAction (Buy/Order…).",
    "aso.action_schema": "Enrich action schemas (Product/Offer, Service, Event).",
    "aso.ai_discovery": "Publish /.well-known/ai.txt and /ai/*.json.",
    "aso.nlweb": "Expose a compliant NLWeb endpoint.",
    "aso.accessible_forms": "Label forms (label/for, aria-label).",
    "aso.openapi": "Expose a documented API (OpenAPI/Swagger).",
    "aso.brand_coherence": "Align name and description between the site and Wikidata.",
    "aso.agent_access": "Allow agent bots in robots.txt.",
    "seo.avg_position": "Improve keyword rankings to reach the top 10 in Google Search.",
    "seo.click_through_rate": "Improve titles and meta descriptions to raise organic CTR above 5%.",
}

_REC_FR: dict[str, str] = {
    "meta.title": "Ajouter un <title> unique de 30–60 caractères sur chaque page.",
    "meta.description": "Rédiger une meta description de 120–158 caractères.",
    "meta.canonical": "Déclarer une URL canonique absolue.",
    "meta.robots": "Retirer les directives noindex des pages à indexer.",
    "meta.title_unique": "Dédupliquer les balises title identiques.",
    "og.complete": "Compléter les balises Open Graph (title, description, image, url, type).",
    "twitter.cards": "Ajouter les Twitter Cards (card, title, description, image).",
    "struct.h1": "N'utiliser qu'un seul H1 par page.",
    "struct.hierarchy": "Corriger la hiérarchie Hn (un H1, aucun niveau sauté).",
    "struct.schema": "Ajouter des données structurées JSON-LD pertinentes.",
    "content.depth": "Enrichir le contenu (viser ≥ 800 mots utiles).",
    "content.text_ratio": "Augmenter le ratio texte/code (alléger le markup).",
    "links.internal": "Ajouter 3 à 100 liens internes pertinents par page.",
    "links.orphans": "Relier les pages orphelines depuis la navigation.",
    "img.alt": "Renseigner l'attribut alt de toutes les images.",
    "crawl.indexable": "Corriger les pages non indexables (statut HTTP, noindex).",
    "crawl.sitemap": "Publier un sitemap.xml valide.",
    "crawl.https": "Servir toutes les pages en HTTPS.",
    "crawl.redirects": "Réduire les chaînes de redirection à un saut maximum.",
    "i18n.hreflang": "Déclarer des hreflang cohérents avec x-default.",
    "perf.lcp": "Optimiser le LCP (≤ 2500 ms).",
    "perf.cls": "Réduire le CLS (≤ 0.1).",
    "perf.inp": "Améliorer l'INP (≤ 200 ms).",
    "perf.lighthouse": "Optimiser la performance (score Lighthouse).",
    "authority.opr": "Acquérir des backlinks et mentions de qualité.",
    "authority.backlinks": "Développer un profil de domaines référents.",
    "gso.faqpage": "Ajouter un schema FAQPage sur les pages de questions.",
    "gso.howto": "Ajouter un schema HowTo sur les tutoriels.",
    "gso.breadcrumb": "Ajouter un BreadcrumbList sur le template.",
    "gso.itemlist": "Structurer les listes via ItemList ou des tableaux.",
    "gso.qa_format": "Formuler des sections question-réponse extractibles.",
    "gso.cwv_eligible": "Faire passer les 3 Core Web Vitals dans les seuils.",
    "aeo.author_credentials": "Déclarer des auteurs avec credentials (Person).",
    "aeo.about_page": "Publier une page À propos détaillée.",
    "aeo.defined_terms": "Ajouter des définitions (DefinedTerm ou glossaire).",
    "aeo.dates_structured": "Exposer datePublished/dateModified en JSON-LD.",
    "aeo.comparison_tables": "Ajouter des tableaux comparatifs.",
    "aeo.answer_directness": "Placer une réponse directe en tête de page.",
    "aeo.kg_presence": "Créer/renforcer l'entité dans Wikidata/Wikipedia.",
    "geo.ssr": "Servir le contenu en rendu serveur (SSR).",
    "geo.noise_ratio": "Augmenter la part de contenu utile vs nav/boilerplate.",
    "geo.entity_density": "Densifier le contenu en entités nommées pertinentes.",
    "geo.primary_sources": "Citer des sources externes primaires (liens sortants).",
    "geo.authors": "Déclarer un auteur structuré (author/Person en JSON-LD).",
    "geo.cross_platform": "Référencer la marque sur ≥4 plateformes (sameAs).",
    "geo.freshness": "Mettre à jour le contenu et exposer dateModified.",
    "geo.citation_rate": "Gagner des citations génératives (contenu de référence citable).",
    "geo.mention_rate": "Renforcer la notoriété de marque (mentions, présence éditoriale).",
    "geo.citation_confidence": "Stabiliser la citation (contenu canonique constant, autorité).",
    "aeo.llm_citation": "Optimiser pour les answer engines (réponses directes, sources fiables).",
    "aso.mcp_readiness": "Exposer un serveur WebMCP (registerTool / toolname).",
    "aso.potential_actions": "Ajouter des potentialAction exécutables (Buy/Order…).",
    "aso.action_schema": "Enrichir les schemas d'action (Product/Offer, Service, Event).",
    "aso.ai_discovery": "Publier /.well-known/ai.txt et /ai/*.json.",
    "aso.nlweb": "Exposer un endpoint NLWeb conforme.",
    "aso.accessible_forms": "Labelliser les formulaires (label/for, aria-label).",
    "aso.openapi": "Exposer une API documentée (OpenAPI/Swagger).",
    "aso.brand_coherence": "Aligner nom et description entre site et Wikidata.",
    "aso.agent_access": "Autoriser les bots d'agents dans robots.txt.",
    "seo.avg_position": (
        "Améliorer le positionnement des mots-clés pour atteindre le top 10 dans Google Search."
    ),
    "seo.click_through_rate": (
        "Améliorer les titres et meta descriptions pour porter le CTR organique au-dessus de 5 %."
    ),
}

# --------------------------------------------------------------------------- #
# Status reasons — why a criterion is not_measured / not_applicable.            #
# --------------------------------------------------------------------------- #
_REASON_EN: dict[str, str] = {
    "no_pages": "No page was crawled.",
    "no_titles": "No title to compare.",
    "link_graph": "Link graph not evaluable (< 2 pages).",
    "no_images": "No image to evaluate.",
    "no_hreflang": "No hreflang declared (assumed monolingual site).",
    "opr_not_configured": "OpenPageRank not configured (OPR key missing).",
    "no_backlink_source": "No referring-domains source configured (Common Crawl coming).",
    "cwv_metric_unavailable": "{metric} unavailable (PSI or field data missing).",
    "lighthouse_unavailable": "Lighthouse score unavailable (PSI not configured).",
    "cwv_unavailable": "Core Web Vitals unavailable (PSI).",
    "longtail": "Long tail not measurable without keyword/SERP data (Phase 4).",
    "serp_not_configured": "SERP API not configured (Phase 4).",
    "wikidata_not_configured": "Wikidata not configured (later slice).",
    "render_mode_unavailable": "Render mode unavailable.",
    "noise_ratio_unavailable": "Content/noise ratio unavailable.",
    "no_text_content": "No page with text content.",
    "no_audit_reference": "Audit reference date unavailable.",
    "no_content_dates": "No structured content date.",
    "ai_discovery_not_probed": "AI discovery endpoints not probed.",
    "nlweb_not_probed": "NLWeb endpoint not probed.",
    "brand_not_measured": "Brand coherence not measured (Wikidata entity absent or disabled).",
    "agent_access_not_evaluated": "Agent bot access not evaluated.",
    "citation_unavailable": "LLM citation tracking unavailable (BYOK API key required).",
    "gsc_not_configured": (
        "Google Search Console not configured"
        " (GSC_SERVICE_ACCOUNT missing or property inaccessible)."
    ),
}

_REASON_FR: dict[str, str] = {
    "no_pages": "Aucune page crawlée.",
    "no_titles": "Aucun title à comparer.",
    "link_graph": "Maillage non évaluable (< 2 pages).",
    "no_images": "Aucune image à évaluer.",
    "no_hreflang": "Aucun hreflang déclaré (site monolingue présumé).",
    "opr_not_configured": "OpenPageRank non configuré (clé OPR absente).",
    "no_backlink_source": "Aucune source de domaines référents configurée (Common Crawl à venir).",
    "cwv_metric_unavailable": "{metric} indisponible (PSI ou données terrain absentes).",
    "lighthouse_unavailable": "Score Lighthouse indisponible (PSI non configuré).",
    "cwv_unavailable": "Core Web Vitals indisponibles (PSI).",
    "longtail": "Longue traîne non mesurable sans données mots-clés/SERP (Phase 4).",
    "serp_not_configured": "API SERP non configurée (Phase 4).",
    "wikidata_not_configured": "Wikidata non configuré (slice ultérieure).",
    "render_mode_unavailable": "Mode de rendu indisponible.",
    "noise_ratio_unavailable": "Ratio contenu/bruit indisponible.",
    "no_text_content": "Aucune page avec contenu textuel.",
    "no_audit_reference": "Date de référence d'audit indisponible.",
    "no_content_dates": "Aucune date de contenu structurée.",
    "ai_discovery_not_probed": "Endpoints de découverte IA non sondés.",
    "nlweb_not_probed": "Endpoint NLWeb non sondé.",
    "brand_not_measured": (
        "Cohérence de marque non mesurée (entité Wikidata absente ou désactivée)."
    ),
    "agent_access_not_evaluated": "Accès des bots d'agents non évalué.",
    "citation_unavailable": "Citation tracking LLM non disponible (clé API BYOK requise).",
    "gsc_not_configured": (
        "Google Search Console non configuré"
        " (GSC_SERVICE_ACCOUNT absent ou propriété inaccessible)."
    ),
}

# --------------------------------------------------------------------------- #
# Explanations — the human-readable line baked into each CriterionResult.       #
# The criterion label is rendered separately by the UI, so it is not repeated   #
# here. `str.format` named fields carry the measured counts.                    #
# --------------------------------------------------------------------------- #
_EXPL_EN: dict[str, str] = {
    "page_conformance": "{passing}/{total} conforming page(s) (mean score {score}).",
    "title_unique": "{unique} unique title(s) across {total} titled page(s).",
    "orphans": "{orphans} orphan page(s) out of {total} (excluding home).",
    "img_alt": "{with_alt}/{total} image(s) with an alt attribute.",
    "indexable": "{indexable}/{total} indexable page(s).",
    "sitemap_valid": "Valid sitemap ({count} URLs).",
    "sitemap_invalid": "No valid sitemap found.",
    "https": "{https}/{total} page(s) served over HTTPS.",
    "hreflang": "{count} page(s) with hreflang (mean score {score}).",
    "authority_opr": "Domain authority (OpenPageRank proxy): {opr}/10.",
    "backlinks": "{count} referring domain(s) (log scale).",
    "cwv": "{metric} = {value}{unit} (good threshold ≤ {good}).",
    "lighthouse": "Lighthouse performance score: {score}/100.",
    "schema_present": "Present on {pages} page(s).",
    "schema_absent": "Absent from the site.",
    "itemlist_present": "Structured list/table present.",
    "itemlist_absent": "No structured list.",
    "qa_present": "Extractable Q&A format present.",
    "qa_absent": "No Q&A format.",
    "cwv_eligible": "All 3 Core Web Vitals within thresholds.",
    "cwv_not_eligible": "At least one Core Web Vital out of threshold.",
    "ai_overview": "AI Overview presence: {score}%.",
    "flag_present": "Present.",
    "flag_absent": "Absent.",
    "author_full": "Identifiable author with credentials.",
    "author_partial": "Identifiable author without structured credentials.",
    "author_none": "No identifiable author.",
    "about_present": "About page: {url}",
    "about_absent": "No About page detected.",
    "answer_directness": "{direct}/{total} page(s) with a lead answer paragraph.",
    "aeo_llm_citation": "Answer engine citation rate: {score}%.",
    "ssr": "{ssr}/{total} page(s) server-rendered (M2 heuristic).",
    "noise_ratio": "Mean content/noise ratio over {pages} page(s).",
    "entity_density": "Estimated entity density over {pages} page(s) (heuristic).",
    "primary_sources": "{with_sources}/{total} page(s) cite an external source.",
    "geo_authors_present": "Structured author present.",
    "geo_authors_absent": "No structured author.",
    "cross_platform": "{count} linked platform(s): {platforms}.",
    "freshness": "Most recent content dated {age} day(s) ago.",
    "citation_rate": (
        "LLM citation rate: {score}% ({prompts} prompt(s) × {reps} rep. × {engines} engine(s))."
    ),
    "mention_rate": "Brand mention rate: {score}%.",
    "citation_confidence": "Citation stability: {score}% over {reps} repetition(s).",
    "webmcp_full": "WebMCP detected (agents can call tools).",
    "webmcp_partial": "Partial WebMCP signals.",
    "webmcp_none": "No WebMCP signal.",
    "actions_executable": "Executable action present: {actions}.",
    "actions_nontransactional": "SearchAction/non-transactional action: {actions}.",
    "actions_none": "No potentialAction.",
    "action_schema": "Rich action types detected: {types}.",
    "accessible_forms": "{total} agent-usable form(s).",
    "openapi_present": "Documented API exposed: {links}.",
    "openapi_absent": "No documented API.",
    "ai_discovery": "{valid}/{total} valid AI discovery endpoint(s).",
    "nlweb": "NLWeb endpoint: {status}.",
    "brand_coherence": "Brand coherence: {score}% (site vs Wikidata).",
    "agent_blocked": "{count} agent bot(s) blocked: {bots}.",
    "agent_all_allowed": "All known agent bots are allowed.",
    "seo_avg_position": (
        "Average position {position} over {queries} tracked keyword(s) (last {days} days)."
    ),
    "seo_ctr": "Organic CTR: {ctr}% ({clicks} click(s) / {impressions} impression(s)).",
}

_EXPL_FR: dict[str, str] = {
    "page_conformance": "{passing}/{total} page(s) conforme(s) (score moyen {score}).",
    "title_unique": "{unique} title(s) unique(s) sur {total} page(s) titrée(s).",
    "orphans": "{orphans} page(s) orpheline(s) sur {total} (hors home).",
    "img_alt": "{with_alt}/{total} image(s) avec attribut alt.",
    "indexable": "{indexable}/{total} page(s) indexable(s).",
    "sitemap_valid": "Sitemap valide ({count} URLs).",
    "sitemap_invalid": "Aucun sitemap valide trouvé.",
    "https": "{https}/{total} page(s) en HTTPS.",
    "hreflang": "{count} page(s) avec hreflang (score moyen {score}).",
    "authority_opr": "Autorité de domaine (proxy OpenPageRank) : {opr}/10.",
    "backlinks": "{count} domaine(s) référent(s) (échelle log).",
    "cwv": "{metric} = {value}{unit} (seuil bon ≤ {good}).",
    "lighthouse": "Score de performance Lighthouse : {score}/100.",
    "schema_present": "Présent sur {pages} page(s).",
    "schema_absent": "Absent du site.",
    "itemlist_present": "Liste/tableau structuré présent.",
    "itemlist_absent": "Aucune liste structurée.",
    "qa_present": "Format Q-R extractible présent.",
    "qa_absent": "Aucun format Q-R.",
    "cwv_eligible": "Les 3 Core Web Vitals sont dans les seuils.",
    "cwv_not_eligible": "Au moins un Core Web Vital hors seuil.",
    "ai_overview": "Présence AI Overview : {score}%.",
    "flag_present": "Présent.",
    "flag_absent": "Absent.",
    "author_full": "Auteur identifiable avec credentials.",
    "author_partial": "Auteur identifiable sans credentials structurés.",
    "author_none": "Aucun auteur identifiable.",
    "about_present": "Page About : {url}",
    "about_absent": "Aucune page About détectée.",
    "answer_directness": "{direct}/{total} page(s) avec paragraphe-réponse en tête.",
    "aeo_llm_citation": "Taux de citation answer engines : {score}%.",
    "ssr": "{ssr}/{total} page(s) en rendu serveur (heuristique M2).",
    "noise_ratio": "Ratio contenu/bruit moyen sur {pages} page(s).",
    "entity_density": "Densité d'entités estimée sur {pages} page(s) (heuristique).",
    "primary_sources": "{with_sources}/{total} page(s) citent une source externe.",
    "geo_authors_present": "Auteur structuré présent.",
    "geo_authors_absent": "Aucun auteur structuré.",
    "cross_platform": "{count} plateforme(s) liée(s) : {platforms}.",
    "freshness": "Contenu le plus récent daté de {age} jour(s).",
    "citation_rate": (
        "Taux de citation LLM : {score}% ({prompts} prompt(s) × {reps} rép. × {engines} moteur(s))."
    ),
    "mention_rate": "Taux de mention de marque : {score}%.",
    "citation_confidence": "Stabilité de citation : {score}% sur {reps} répétition(s).",
    "webmcp_full": "WebMCP détecté (agents peuvent appeler des outils).",
    "webmcp_partial": "Signaux WebMCP partiels.",
    "webmcp_none": "Aucun signal WebMCP.",
    "actions_executable": "Action exécutable présente : {actions}.",
    "actions_nontransactional": "SearchAction/action non transactionnelle : {actions}.",
    "actions_none": "Aucun potentialAction.",
    "action_schema": "Types d'action riches détectés : {types}.",
    "accessible_forms": "{total} formulaire(s) exploitable(s) par un agent.",
    "openapi_present": "API documentée exposée : {links}.",
    "openapi_absent": "Aucune API documentée.",
    "ai_discovery": "{valid}/{total} endpoint(s) de découverte IA valides.",
    "nlweb": "Endpoint NLWeb : {status}.",
    "brand_coherence": "Cohérence de marque : {score}% (site vs Wikidata).",
    "agent_blocked": "{count} bot(s) d'agent bloqué(s) : {bots}.",
    "agent_all_allowed": "Tous les bots d'agents connus sont autorisés.",
    "seo_avg_position": (
        "Position moyenne {position} sur {queries} mot(s)-clé(s) suivi(s) (derniers {days} jours)."
    ),
    "seo_ctr": "CTR organique : {ctr} % ({clicks} clic(s) / {impressions} impression(s)).",
}

# Misc shared words.
_WORD_EN: dict[str, str] = {"none": "none"}
_WORD_FR: dict[str, str] = {"none": "aucune"}

_EN: dict[str, str] = {
    **{f"rec.{k}": v for k, v in _REC_EN.items()},
    "rec.generic": "Fix the {key} criterion.",
    **{f"reason.{k}": v for k, v in _REASON_EN.items()},
    **{f"expl.{k}": v for k, v in _EXPL_EN.items()},
    **{f"word.{k}": v for k, v in _WORD_EN.items()},
}

_FR: dict[str, str] = {
    **{f"rec.{k}": v for k, v in _REC_FR.items()},
    "rec.generic": "Corriger le critère {key}.",
    **{f"reason.{k}": v for k, v in _REASON_FR.items()},
    **{f"expl.{k}": v for k, v in _EXPL_FR.items()},
    **{f"word.{k}": v for k, v in _WORD_FR.items()},
}

CATALOG: dict[str, dict[str, str]] = {"en": _EN, "fr": _FR}
