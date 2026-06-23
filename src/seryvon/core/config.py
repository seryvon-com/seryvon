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

    # Crawl (limits per audit are in CrawlConfig; user_agent and timeout are global)
    user_agent: str = "Seryvon/0.1 (+https://seryvon.com/bot)"
    request_timeout: float = 15.0

    # BYOK encryption (Fernet). Empty => BYOK features disabled (Phase 0).
    secret_key: str = ""

    # Object store for raw artifacts (Observe layer, C-P2). Keys read from the
    # S3_* convention (deployment .env). Empty endpoint/bucket => in-memory store
    # (offline default; no artifact persistence).
    s3_endpoint_url: str = Field(default="", validation_alias="S3_ENDPOINT")
    s3_bucket: str = Field(default="", validation_alias="S3_BUCKET")
    s3_region: str = Field(default="", validation_alias="S3_REGION")
    s3_access_key: str = Field(default="", validation_alias="S3_ACCESS_KEY")
    s3_secret_key: str = Field(default="", validation_alias="S3_SECRET_KEY")

    # PageSpeed Insights (BYOK). Key read from the PSI_API_KEY variable (document
    # 04 convention); empty => perf.* criteria not_measured.
    # PSI runs Lighthouse in the cloud — 60 s is the safe floor (mobile audit
    # regularly takes 30–50 s; 15 s general timeout is way too short).
    psi_api_key: str = Field(default="", validation_alias="PSI_API_KEY")
    pagespeed_strategy: str = DEFAULT_PSI_STRATEGY
    psi_timeout: float = Field(default=60.0, validation_alias="PSI_TIMEOUT")

    # OpenPageRank (BYOK, deprecated — acquired by Keywords Everywhere).
    opr_api_key: str = Field(default="", validation_alias="OPR_API_KEY")

    # DataForSEO (BYOK). Stored as "login:password". Feeds authority.opr
    # (domain_rank normalised 0–10) and authority.backlinks (referring_domains).
    dataforseo_api_key: str = Field(default="", validation_alias="DATAFORSEO_API_KEY")

    # Wikidata (free, keyless). Disableable => aeo.kg_presence /
    # aso.brand_coherence not_measured.
    wikidata_enabled: bool = True

    # Google Search Console (BYOK, M10). Service account JSON (stringified).
    # Empty => seo.avg_position / seo.click_through_rate stay not_measured.
    gsc_service_account: str = Field(default="", validation_alias="GSC_SERVICE_ACCOUNT")

    # Playwright rendering (optional, geo.ssr). Install: `playwright install chromium`.
    # Disabled by default — opt-in via PLAYWRIGHT_ENABLED=true.
    playwright_enabled: bool = Field(default=False, validation_alias="PLAYWRIGHT_ENABLED")
    playwright_timeout: float = Field(default=30.0, validation_alias="PLAYWRIGHT_TIMEOUT")

    # LLM citation tracking keys (BYOK, M4). Each empty => that engine is skipped;
    # with no key at all, geo.citation_* / aeo.llm_citation stay not_measured.
    perplexity_api_key: str = Field(default="", validation_alias="PERPLEXITY_API_KEY")
    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    anthropic_api_key: str = Field(default="", validation_alias="ANTHROPIC_API_KEY")
    gemini_api_key: str = Field(default="", validation_alias="GEMINI_API_KEY")

    # SERP / AI Overview connector (BYOK, M9). Empty => gso.ai_overview_presence
    # stays not_measured. SERP_PROVIDER selects the adapter (default: "serpapi").
    serp_api_key: str = Field(default="", validation_alias="SERP_API_KEY")
    serp_provider: str = Field(default="serpapi", validation_alias="SERP_PROVIDER")


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
    # Locale for produced text (recommendations, explanations…). English base, FR
    # second locale. Presentation only — never affects scores (see seryvon.i18n).
    locale: str = "en"

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
