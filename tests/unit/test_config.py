# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
# Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
"""Tests de la configuration (défauts, chargement YAML, surcharges)."""

from __future__ import annotations

from pathlib import Path

from seryvon.core.config import DEFAULT_PILLAR_WEIGHTS, AuditConfig


def test_default_weights_sum_to_one() -> None:
    assert round(sum(DEFAULT_PILLAR_WEIGHTS.values()), 6) == 1.0


def test_default_config() -> None:
    cfg = AuditConfig.default()
    assert cfg.pillar_weights["seo"] == 0.30
    assert cfg.pillar_weights["aso"] == 0.15


def test_from_yaml_overrides(tmp_path: Path) -> None:
    yaml_path = tmp_path / "seryvon.config.yaml"
    yaml_path.write_text(
        """
pillars:
  weights:
    aso: 0.25
criteria_overrides:
  meta.title:
    weight: 3.0
crawl:
  max_pages: 50
""",
        encoding="utf-8",
    )
    cfg = AuditConfig.from_yaml(yaml_path)
    assert cfg.pillar_weights["aso"] == 0.25
    # Les autres poids restent aux valeurs par défaut.
    assert cfg.pillar_weights["seo"] == 0.30
    assert cfg.criteria_overrides["meta.title"]["weight"] == 3.0
    assert cfg.crawl.max_pages == 50


def test_from_yaml_empty_file(tmp_path: Path) -> None:
    yaml_path = tmp_path / "empty.yaml"
    yaml_path.write_text("", encoding="utf-8")
    cfg = AuditConfig.from_yaml(yaml_path)
    assert cfg.pillar_weights == DEFAULT_PILLAR_WEIGHTS
