# Seryvon — PDF layout helper tests. AGPL-3.0-or-later.
"""Tests for PDF CSS injection and self-contained branding."""

from seryvon.reporting.pdf_report import _add_branding, _inject_print_css


def test_print_css_is_injected_before_style_close() -> None:
    html = "<style>body{color:black}</style>"
    result = _inject_print_css(html)
    assert "size: A4 portrait" in result
    assert result.index("size: A4 portrait") < result.index("</style>")


def test_branding_embeds_logo_and_public_links() -> None:
    result = _add_branding(
        '<h1>Audit Seryvon</h1><p class="domain">example.com</p>\n  <div class="global">72</div>'
    )
    assert "data:image/png;base64," in result
    assert 'alt="Seryvon"' in result
    assert "https://seryvon.com" in result
    assert "https://github.com/seryvon-com/seryvon" in result
