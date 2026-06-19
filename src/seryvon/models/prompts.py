# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Prompt-set models (module M4b, document 08).

The prompt set is the measurement instrument of citation tracking: a versioned,
intent-balanced collection of queries sent to the LLMs. Generated deterministically
from the crawl's theme profile (Voie A templates); LLM-assisted generation (Voie B)
and user validation come later. Prompt text is in French (product content).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class PromptIntent(StrEnum):
    """Search-intent category of a prompt (document 08 §4.1)."""

    DEFINITIONAL = "definitional"
    COMPARATIVE = "comparative"
    RECOMMENDATION = "recommendation"
    EXPLANATORY = "explanatory"
    LISTING = "listing"
    USE_CASE = "use_case"
    NEWS = "news"


class Prompt(BaseModel):
    """A single generated prompt with its provenance and quality score."""

    text: str
    intent: PromptIntent
    source: str = "template"  # template / llm / user
    quality_score: float = 0.0  # 0–1 (document 08 §5)


class ThemeProfile(BaseModel):
    """Theme profile derived from the crawl signals (document 08 §3)."""

    domain: str
    topics: list[str] = Field(default_factory=list)
    entities: list[str] = Field(default_factory=list)
    content_type: str = "general"
    brand: str | None = None


class PromptSet(BaseModel):
    """Versioned, intent-balanced set of prompts (document 08 §8)."""

    version: int = 1
    domain: str
    generated_by: str = "templates"  # templates / llm_assisted / manual / mixed
    theme_profile: ThemeProfile
    prompts: list[Prompt] = Field(default_factory=list)
    tracked_competitors: list[str] = Field(default_factory=list)
