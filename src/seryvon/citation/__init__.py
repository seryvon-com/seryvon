# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Module M4 — citation tracking LLM (document 07).

`aggregate` : cœur pur et déterministe (parsing/normalisation + agrégation des
`LlmResponse` en `CitationMetrics`). Les connecteurs réseau (Perplexity, OpenAI…)
arrivent dans les slices suivantes et alimentent cet agrégateur.
"""

from seryvon.citation.aggregate import (
    aggregate_citations,
    brand_mentioned,
    domain_matches,
    registrable_domain,
)

__all__ = [
    "aggregate_citations",
    "brand_mentioned",
    "domain_matches",
    "registrable_domain",
]
