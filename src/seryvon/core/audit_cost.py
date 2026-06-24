# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""Audit cost estimator — pure function, no I/O.

Estimates the spend of a single audit BEFORE launching it, based on which
BYOK connectors are active in the provided settings. Figures are indicative
2026 USD placeholders; a zero cost means the connector is free or inactive.

Cost table rationale:
  - PSI / OPR / Wikidata / GSC : free (gratuit ou sur quota offert)
  - DataForSEO Technologies endpoint : $0.01/req, 1 call/audit
  - DataForSEO Labs fallback        : $0.01/req, triggered when first fails
  - SerpAPI                         : ~$0.015/search × 3 probes = $0.045/audit
  - LLM citation (separate trigger) : see citation/cost.py; 0 here (not part of audit)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from seryvon.core.config import Settings


@dataclass(frozen=True)
class ConnectorLine:
    """One line in the cost breakdown."""

    connector: str
    active: bool
    calls: int
    unit_usd: float
    total_usd: float
    note: str = ""


@dataclass
class AuditCostEstimate:
    """Estimated cost of a single audit run."""

    currency: str = "USD"
    total_usd: float = 0.0
    indicative: bool = True  # always True: prices are placeholders
    lines: list[ConnectorLine] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "currency": self.currency,
            "total_usd": round(self.total_usd, 4),
            "indicative": self.indicative,
            "lines": [
                {
                    "connector": ln.connector,
                    "active": ln.active,
                    "calls": ln.calls,
                    "unit_usd": ln.unit_usd,
                    "total_usd": ln.total_usd,
                    "note": ln.note,
                }
                for ln in self.lines
            ],
        }


# Indicative 2026 USD prices — override via custom Settings subclass or env.
_DATAFORSEO_PER_CALL = 0.01
_SERPAPI_PER_SEARCH = 0.015
_SERPAPI_PROBES = 3  # branded + definitional + evaluative


def estimate_audit_cost(settings: Settings) -> AuditCostEstimate:
    """Return an indicative cost breakdown for one audit given active BYOK keys.

    Pure: reads only the settings object, performs no network calls.
    Citation-tracking LLM cost is NOT included here (separate trigger,
    see citation.cost.estimate_cost).
    """
    lines: list[ConnectorLine] = []
    total = 0.0

    # --- Free connectors (always noted for transparency) ---
    free: list[tuple[str, bool, str]] = [
        ("psi", bool(settings.psi_api_key), "Free quota (Google, 25k req/day)"),
        ("opr", bool(settings.opr_api_key), "Free (openpagerank.com)"),
        ("wikidata", settings.wikidata_enabled, "Free (no key required)"),
        ("gsc", bool(settings.gsc_service_account), "Free (your own GSC data)"),
    ]
    for name, active, note in free:
        lines.append(ConnectorLine(
            connector=name, active=active,
            calls=1 if active else 0,
            unit_usd=0.0, total_usd=0.0, note=note,
        ))

    # --- DataForSEO ---
    dfs_active = bool(settings.dataforseo_api_key)
    if dfs_active:
        # 1 primary call + 1 fallback (worst case); best case = 1 call
        dfs_calls = 2
        dfs_total = dfs_calls * _DATAFORSEO_PER_CALL
        total += dfs_total
    else:
        dfs_calls = 0
        dfs_total = 0.0
    lines.append(ConnectorLine(
        connector="dataforseo",
        active=dfs_active,
        calls=dfs_calls,
        unit_usd=_DATAFORSEO_PER_CALL,
        total_usd=round(dfs_total, 4),
        note="Technologies + Labs fallback (worst case 2 calls)",
    ))

    # --- SerpAPI ---
    serp_active = bool(settings.serp_api_key)
    if serp_active:
        serp_total = _SERPAPI_PROBES * _SERPAPI_PER_SEARCH
        total += serp_total
    else:
        serp_total = 0.0
    lines.append(ConnectorLine(
        connector="serpapi",
        active=serp_active,
        calls=_SERPAPI_PROBES if serp_active else 0,
        unit_usd=_SERPAPI_PER_SEARCH,
        total_usd=round(serp_total, 4),
        note=f"{_SERPAPI_PROBES} SERP probes (branded + definitional + evaluative)",
    ))

    # --- LLM citation (informational only — not triggered by the audit itself) ---
    llm_engines = [e for e in ("perplexity", "openai", "anthropic", "gemini")
                   if getattr(settings, f"{e}_api_key", "")]
    lines.append(ConnectorLine(
        connector="llm_citation",
        active=bool(llm_engines),
        calls=0,
        unit_usd=0.0,
        total_usd=0.0,
        note=(
            f"Not included in audit cost — triggered separately "
            f"(active engines: {', '.join(llm_engines) or 'none'})"
        ),
    ))

    return AuditCostEstimate(total_usd=round(total, 4), lines=lines)
