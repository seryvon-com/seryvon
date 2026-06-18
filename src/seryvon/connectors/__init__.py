"""Connecteurs d'APIs externes (BYOK) : PageSpeed Insights, OpenPageRank, etc.

Couche de collecte : chaque connecteur fait des I/O et renvoie une structure
pure, mappée dans `ExternalSignals`. Un connecteur non configuré (pas de clé) =>
critères dépendants `not_measured` (jamais d'estimation).
"""

from seryvon.connectors.ai_discovery import probe_ai_discovery, probe_nlweb
from seryvon.connectors.openpagerank import (
    OpenPageRankResult,
    fetch_openpagerank,
    parse_openpagerank,
)
from seryvon.connectors.pagespeed import PageSpeedResult, fetch_pagespeed, parse_pagespeed
from seryvon.connectors.wikidata import (
    WikidataResult,
    brand_coherence,
    fetch_wikidata,
    parse_wikidata,
)

__all__ = [
    "OpenPageRankResult",
    "PageSpeedResult",
    "WikidataResult",
    "brand_coherence",
    "fetch_openpagerank",
    "fetch_pagespeed",
    "fetch_wikidata",
    "parse_openpagerank",
    "parse_pagespeed",
    "parse_wikidata",
    "probe_ai_discovery",
    "probe_nlweb",
]
