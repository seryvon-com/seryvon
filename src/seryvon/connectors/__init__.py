"""Connecteurs d'APIs externes (BYOK) : PageSpeed Insights, OpenPageRank, etc.

Couche de collecte : chaque connecteur fait des I/O et renvoie une structure
pure, mappée dans `ExternalSignals`. Un connecteur non configuré (pas de clé) =>
critères dépendants `not_measured` (jamais d'estimation).
"""

from seryvon.connectors.pagespeed import PageSpeedResult, fetch_pagespeed, parse_pagespeed

__all__ = ["PageSpeedResult", "fetch_pagespeed", "parse_pagespeed"]
