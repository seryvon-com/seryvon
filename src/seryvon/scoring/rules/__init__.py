# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Modules de règles. Les importer ici suffit à les auto-enregistrer (@register).

À mesure que de nouveaux modules de règles sont ajoutés (geo, gso, aeo, aso),
il suffit de les importer dans ce fichier — le moteur les découvre via `RULES`.
"""

from seryvon.scoring.rules import aeo, aso, authority, geo, gso, perf, seo

__all__ = ["aeo", "aso", "authority", "geo", "gso", "perf", "seo"]
