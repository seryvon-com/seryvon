"""Génération des rapports (JSON source de vérité + HTML ; PDF/Markdown à venir)."""

from seryvon.reporting.html_report import report_to_html
from seryvon.reporting.json_report import report_to_json

__all__ = ["report_to_html", "report_to_json"]
