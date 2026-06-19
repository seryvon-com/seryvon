# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Rule modules. Importing them here is enough to self-register them (@register).

As new rule modules are added (geo, gso, aeo, aso), simply import them in this
file — the engine discovers them via `RULES`.
"""

from seryvon.scoring.rules import aeo, aso, authority, geo, gso, perf, seo

__all__ = ["aeo", "aso", "authority", "geo", "gso", "perf", "seo"]
