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

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from seryvon.models.report import AuditReport

_PRINT_CSS = """
@page {
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
.pillars {
  page-break-after: avoid;
}
.pillar {
  box-shadow: none !important;
  border: 1px solid #d0d7de;
}
table {
  page-break-inside: auto;
}
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
    html_str = _inject_print_css(html_str)
    result: bytes = HTML(string=html_str).write_pdf()
    return result
