# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Fixtures de test partagées."""

from __future__ import annotations

import pytest

from seryvon.models.signals import PageSignals, SignalBundle


@pytest.fixture(autouse=True)
def _stub_agentic_probes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neutralise les sondes réseau ASO (ai discovery / NLWeb) dans tous les tests."""
    from seryvon.core import audit as audit_module

    async def _no_discovery(origin: str, **kwargs: object) -> dict[str, bool]:
        return {}

    async def _no_nlweb(origin: str, **kwargs: object) -> str:
        return "absent"

    monkeypatch.setattr(audit_module, "probe_ai_discovery", _no_discovery, raising=False)
    monkeypatch.setattr(audit_module, "probe_nlweb", _no_nlweb, raising=False)


@pytest.fixture
def sample_html() -> str:
    """HTML minimal mais réaliste, avec title optimal et un bloc JSON-LD."""
    return """<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <title>Seryvon — Audit SEO GEO GSO AEO ASO déterministe</title>
  <meta name="description" content="Outil d'audit web sur cinq piliers, mesuré et reproductible.">
  <link rel="canonical" href="https://example.com/">
  <script type="application/ld+json">
  {"@context":"https://schema.org","@type":"Organization","name":"Seryvon"}
  </script>
</head>
<body>
  <h1>Audit web déterministe</h1>
  <h2>Cinq piliers</h2>
  <p>Un paragraphe de contenu avec quelques mots pour le ratio texte.</p>
  <a href="/about">À propos</a>
  <a href="https://external.example.org">Lien externe</a>
  <img src="logo.png" alt="Logo Seryvon">
  <img src="deco.png">
</body>
</html>"""


@pytest.fixture
def bundle_with_title() -> SignalBundle:
    """Bundle dont la home a un title de longueur optimale."""
    return SignalBundle(
        domain="example.com",
        pages=[PageSignals(url="https://example.com/", title="Un titre tout à fait correct ici")],
    )


@pytest.fixture
def bundle_no_title() -> SignalBundle:
    """Bundle dont la home n'a pas de title."""
    return SignalBundle(
        domain="example.com",
        pages=[PageSignals(url="https://example.com/", title=None)],
    )
