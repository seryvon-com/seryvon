# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""JSON export of the report ("source of truth" format — document 05, §7).

The HTML/PDF/Markdown formats (document 02, M7) derive from this JSON and were
added in Phases 1–2.
"""

from __future__ import annotations

from seryvon.models.report import AuditReport


def report_to_json(report: AuditReport, *, indent: int = 2) -> str:
    """Serialize a report into deterministic JSON (ordered keys)."""
    return report.model_dump_json(indent=indent)
