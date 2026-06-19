# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Application configuration.

Two levels:
- `Settings`: environment variables (infra, secrets, crawl). Prefix `SERYVON_`.
- `AuditConfig`: weights and thresholds loaded from a YAML per audit
  (see `seryvon.config.yaml` in document 04). Designed to be overridable without
  touching the code, per requirement EF-11.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Default PSI strategy (decision D4: home page only, mobile-first).
DEFAULT_PSI_STRATEGY = "mobile"


class Settings(BaseSettings):
    """Infrastructure configuration, read from the environment / `.env`."""

    model_config = SettingsConfigDict(
        env_prefix="SERYVON_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Persistence / queues
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

    # BYOK encryption (Fernet). Empty => BYOK features disabled (Phase 0).
    secret_key: str = ""

    # PageSpeed Insights (BYOK). Key read from the PSI_API_KEY variable (document
    # 04 convention); empty => perf.* criteria not_measured.
    psi_api_key: str = Field(default="", validation_alias="PSI_API_KEY")
    pagespeed_strategy: str = DEFAULT_PSI_STRATEGY

    # OpenPageRank (BYOK). Key read from OPR_API_KEY; empty => authority.opr
    # not_measured.
    opr_api_key: str = Field(default="", validation_alias="OPR_API_KEY")

    # Wikidata (free, keyless). Disableable => aeo.kg_presence /
    # aso.brand_coherence not_measured.
    wikidata_enabled: bool = True


@lru_cache
def get_settings() -> Settings:
    """Cached singleton of the infrastructure settings."""
    return Settings()


# Default pillar weights (document 04, §1). Sum = 1.00.
DEFAULT_PILLAR_WEIGHTS: dict[str, float] = {
    "seo": 0.30,
    "geo": 0.22,
    "gso": 0.18,
    "aeo": 0.15,
    "aso": 0.15,
}


class CrawlConfig(BaseModel):
    """Crawl limits, overridable per audit or via the CLI."""

    max_depth: int = 3
    max_pages: int = 300
    respect_robots: bool = True
    user_agent: str = "Seryvon/0.1 (+https://seryvon.com/bot)"


class AuditConfig(BaseModel):
    """Configuration of an audit: weights, criterion overrides, thresholds.

    Loaded from YAML; any missing key falls back to the default values. The
    `config_digest` (computed elsewhere) guarantees reproducibility (document 05, §8).
    """

    pillar_weights: dict[str, float] = Field(default_factory=lambda: dict(DEFAULT_PILLAR_WEIGHTS))
    criteria_overrides: dict[str, dict[str, Any]] = Field(default_factory=dict)
    thresholds: dict[str, dict[str, Any]] = Field(default_factory=dict)
    crawl: CrawlConfig = Field(default_factory=CrawlConfig)

    @classmethod
    def from_yaml(cls, path: str | Path) -> AuditConfig:
        """Load an audit configuration from a YAML file."""
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
        """Default configuration (used when no YAML is provided)."""
        return cls()
