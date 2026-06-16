# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Configuration applicative.

Deux niveaux :
- `Settings` : variables d'environnement (infra, secrets, crawl). Préfixe `SERYVON_`.
- `AuditConfig` : pondérations et seuils chargés depuis un YAML par audit
  (cf. `seryvon.config.yaml` du document 04). Conçu pour être surchargeable
  sans toucher au code, conformément à l'exigence EF-11.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration d'infrastructure, lue depuis l'environnement / `.env`."""

    model_config = SettingsConfigDict(
        env_prefix="SERYVON_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Persistance / files
    database_url: str = "postgresql+psycopg://seryvon:seryvon@localhost:5432/seryvon"
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Crawl
    user_agent: str = "Seryvon/0.1 (+https://seryvon.com/bot)"
    max_pages: int = 200
    max_depth: int = 3
    respect_robots: bool = True
    request_timeout: float = 15.0

    # Chiffrement BYOK (Fernet). Vide => fonctions BYOK désactivées (Phase 0).
    secret_key: str = ""


@lru_cache
def get_settings() -> Settings:
    """Singleton mis en cache des settings d'infrastructure."""
    return Settings()


# Pondérations par défaut des piliers (document 04, §1). Somme = 1.00.
DEFAULT_PILLAR_WEIGHTS: dict[str, float] = {
    "seo": 0.30,
    "geo": 0.22,
    "gso": 0.18,
    "aeo": 0.15,
    "aso": 0.15,
}


class CrawlConfig(BaseModel):
    """Limites de crawl, surchargeables par audit ou via CLI."""

    max_depth: int = 3
    max_pages: int = 300
    respect_robots: bool = True
    user_agent: str = "Seryvon/0.1 (+https://seryvon.com/bot)"


class AuditConfig(BaseModel):
    """Configuration d'un audit : pondérations, surcharges de critères, seuils.

    Chargée depuis YAML ; toute clé absente retombe sur les valeurs par défaut.
    Le `config_digest` (calculé ailleurs) garantit la reproductibilité (document 05, §8).
    """

    pillar_weights: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_PILLAR_WEIGHTS))
    criteria_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    thresholds: dict[str, dict[str, Any]] = Field(default_factory=dict)
    crawl: CrawlConfig = Field(default_factory=CrawlConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> AuditConfig:
        """Charge une configuration d'audit depuis un fichier YAML."""
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
        pillars = raw.get("pillars", {})
        return cls(
            pillar_weights={**DEFAULT_PILLAR_WEIGHTS, **pillars.get("weights", {})},
            criteria_overrides=raw.get("criteria_overrides", {}),
            thresholds=raw.get("thresholds", {}),
            crawl=CrawlConfig(**raw.get("crawl", {})),
        )

    @classmethod
    def default(cls) -> AuditConfig:
        """Configuration par défaut (utilisée quand aucun YAML n'est fourni)."""
        return cls()
