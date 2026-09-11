# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""PDF export via WeasyPrint (optional extra [pdf]).

Converts the existing HTML report to a print-optimised PDF. No new template:
`report_to_html` produces the source; a `<style>` injection handles page layout,
removes decorative shadows and backgrounds, and ensures readable print typography.

Install:  pip install "seryvon[pdf]"
Requires: WeasyPrint ≥ 62 (fonttools, brotli, pydyf bundled; no system cairo needed
          on macOS/Windows; on Linux install libpango-1.0 + libharfbuzz).
"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from seryvon.models.report import AuditReport

_PRINT_CSS = """
@page {
  size: A4 portrait;
  margin: 18mm 16mm;
  @bottom-right {
    content: "Page " counter(page) " / " counter(pages);
    font-size: 8pt;
    color: #6e7781;
  }
}
body {
  background: #fff !important;
  color: #1f2328 !important;
  font-size: 9pt;
}
header {
  background: #0d1117 !important;
  -webkit-print-color-adjust: exact;
  print-color-adjust: exact;
  page-break-after: avoid;
}
header h1 { display: flex; align-items: center; gap: 10pt; }
header h1 img { width: 42pt; height: 30pt; object-fit: contain; }
.brand-name { font-size: 22pt; letter-spacing: -.5pt; }
.report-links { margin: 6pt 0 0; font-size: 8pt; }
.report-links a { color: #9da7b3; margin-right: 10pt; }
.pillars {
  page-break-after: avoid;
}
.pillar {
  box-shadow: none !important;
  border: 1px solid #d0d7de;
}
table {
  width: 100%;
  table-layout: fixed;
  page-break-inside: auto;
  font-size: 6.5pt;
}
table.criteria-table col.criterion { width: 10%; }
table.criteria-table col.status { width: 15%; }
table.criteria-table col.score,
table.criteria-table col.weight { width: 7%; }
table.criteria-table col.explanation { width: 22%; }
table.criteria-table col.threshold { width: 12%; }
table.criteria-table col.measured { width: 13%; }
table.criteria-table col.source { width: 14%; }
table.criteria-table col.priority { width: 10%; }
table.criteria-table col.severity { width: 12%; }
table.criteria-table col.impact,
table.criteria-table col.effort { width: 8%; }
table.criteria-table col.recommendation { width: 54%; }
th, td {
  box-sizing: border-box;
  overflow-wrap: anywhere;
  word-break: break-word;
}
td.key { width: 10%; }
td.mono { white-space: normal; }
.badge { white-space: nowrap; }
tr {
  page-break-inside: avoid;
  page-break-after: auto;
}
thead {
  display: table-header-group;
}
a { color: inherit; text-decoration: none; }
"""

_INJECT_MARKER = "</style>"


def _inject_print_css(html: str) -> str:
    """Append print CSS just before the closing </style> tag."""
    return html.replace(_INJECT_MARKER, _PRINT_CSS + _INJECT_MARKER, 1)


def _add_branding(html: str) -> str:
    """Embed the official logo and public project links in the self-contained PDF."""
    logo_path = Path(__file__).with_name("assets") / "logo-mark.png"
    logo_uri = ""
    if logo_path.is_file():
        encoded = base64.b64encode(logo_path.read_bytes()).decode("ascii")
        logo_uri = f"data:image/png;base64,{encoded}"
    logo = f'<img src="{logo_uri}" alt="Seryvon">' if logo_uri else ""
    heading = f'<h1>{logo}<span class="brand-name">seryvon</span></h1>'
    links = (
        '<p class="report-links"><a href="https://seryvon.com">Site officiel · seryvon.com</a>'
        '<a href="https://github.com/seryvon-com/seryvon">Code source · GitHub</a></p>'
    )
    branded = html.replace("<h1>Audit Seryvon</h1>", heading, 1)
    return branded.replace(
        '</p>\n  <div class="global',
        "</p>\n  " + links + '\n  <div class="global',
        1,
    )


def report_to_pdf(report: AuditReport) -> bytes:
    """Convert an AuditReport to a PDF byte string.

    Raises ``ImportError`` if WeasyPrint is not installed (``pip install 'seryvon[pdf]'``).
    """
    try:
        from weasyprint import HTML
    except ImportError as exc:
        raise ImportError(
            "PDF export requires WeasyPrint — install it with: pip install 'seryvon[pdf]'"
        ) from exc

    from seryvon.reporting.html_report import report_to_html

    html_str = report_to_html(report)
    html_str = _add_branding(html_str)
    html_str = _inject_print_css(html_str)
    result: bytes = HTML(string=html_str).write_pdf()
    return result
