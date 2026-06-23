"""External API connectors (BYOK): PageSpeed Insights, OpenPageRank, etc.

Collection layer: each connector performs I/O and returns a pure structure,
mapped into `ExternalSignals`. An unconfigured connector (no key) => dependent
criteria `not_measured` (never estimated).
"""

from seryvon.connectors.ai_discovery import probe_ai_discovery, probe_nlweb
from seryvon.connectors.dataforseo import DataForSeoResult, fetch_dataforseo, parse_dataforseo
from seryvon.connectors.gsc import fetch_gsc, parse_gsc
from seryvon.connectors.openpagerank import (
    OpenPageRankResult,
    fetch_openpagerank,
    parse_openpagerank,
)
from seryvon.connectors.pagespeed import PageSpeedResult, fetch_pagespeed, parse_pagespeed
from seryvon.connectors.serp import aggregate_aio, build_queries, fetch_serp_aio, parse_serp_aio
from seryvon.connectors.wikidata import (
    WikidataResult,
    brand_coherence,
    fetch_wikidata,
    parse_wikidata,
)
from seryvon.models.signals import AioMetrics, AioResult, AioSource, GscResult

__all__ = [
    "AioMetrics",
    "AioResult",
    "AioSource",
    "DataForSeoResult",
    "GscResult",
    "OpenPageRankResult",
    "PageSpeedResult",
    "WikidataResult",
    "aggregate_aio",
    "brand_coherence",
    "build_queries",
    "fetch_dataforseo",
    "fetch_gsc",
    "fetch_openpagerank",
    "fetch_pagespeed",
    "fetch_serp_aio",
    "fetch_wikidata",
    "parse_dataforseo",
    "parse_gsc",
    "parse_openpagerank",
    "parse_pagespeed",
    "parse_serp_aio",
    "parse_wikidata",
    "probe_ai_discovery",
    "probe_nlweb",
]
