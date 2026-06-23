"""Report generation: JSON (source of truth), HTML, Markdown, PDF."""

from seryvon.reporting.html_report import report_to_html
from seryvon.reporting.json_report import report_to_json
from seryvon.reporting.markdown_report import report_to_markdown
from seryvon.reporting.pdf_report import report_to_pdf

__all__ = ["report_to_html", "report_to_json", "report_to_markdown", "report_to_pdf"]
