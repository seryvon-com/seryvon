# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Seryvon — moteur d'audit déterministe sur 5 piliers (SEO/GEO/GSO/AEO/ASO)."""

__version__ = "0.1.0.dev0"

# Liste canonique des piliers, dans l'ordre de pondération par défaut.
PILLARS: tuple[str, ...] = ("seo", "geo", "gso", "aeo", "aso")
