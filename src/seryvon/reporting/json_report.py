# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Export JSON du rapport (format « source de vérité » — document 05, §7).

Les formats HTML/PDF/Markdown (document 02, M7) dérivent de ce JSON et seront
ajoutés en Phase 1–2.
"""

from __future__ import annotations

from seryvon.models.report import AuditReport


def report_to_json(report: AuditReport, *, indent: int = 2) -> str:
    """Sérialise un rapport en JSON déterministe (clés ordonnées)."""
    return report.model_dump_json(indent=indent)
