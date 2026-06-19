"""Report generation: JSON (source of truth), HTML, Markdown (PDF coming later)."""

from seryvon.reporting.html_report import report_to_html
from seryvon.reporting.json_report import report_to_json
from seryvon.reporting.markdown_report import report_to_markdown

__all__ = ["report_to_html", "report_to_json", "report_to_markdown"]
