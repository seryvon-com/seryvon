# Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
# Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version. See <https://www.gnu.org/licenses/>.
"""HTML export of the report (decision D5).

Self-contained report (inline CSS) derived from the JSON source of truth: global
score, gauges for the 5 pillars, then a table of criteria grouped by pillar with
status, score, threshold, explanation and evidence (visible traceability —
requirement O4). The rendered report text itself stays in French (product output).

Security: `autoescape=True` is mandatory — the report embeds crawled third-party
content (titles, URLs, measured values) that could contain malicious HTML. The
rendering is deterministic (same data => same HTML).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from jinja2 import Environment

from seryvon.models.criterion import CriterionResult
from seryvon.models.enums import (
    STATUS_OK_THRESHOLD,
    STATUS_WARNING_THRESHOLD,
    Status,
)
from seryvon.models.report import AuditReport

_STATUS_CSS: dict[Status, str] = {
    Status.OK: "ok",
    Status.WARNING: "warning",
    Status.CRITICAL: "critical",
    Status.NOT_MEASURED: "nm",
    Status.NOT_APPLICABLE: "nm",
}


def _band(score: float) -> str:
    """CSS class of an aggregate score (same thresholds as the statuses)."""
    if score >= STATUS_OK_THRESHOLD:
        return "ok"
    if score >= STATUS_WARNING_THRESHOLD:
        return "warning"
    return "critical"


def _row(criterion: CriterionResult) -> dict[str, Any]:
    return {
        "key": criterion.key,
        "status": criterion.status.value,
        "status_css": _STATUS_CSS[criterion.status],
        "score": criterion.score,
        "weight": criterion.weight,
        "explanation": criterion.explanation,
        "threshold": criterion.threshold,
        "raw_value": criterion.raw_value,
        "evidence": criterion.evidence,
    }


_TEMPLATE = """<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Audit Seryvon — {{ report.domain }}</title>
<style>
  :root { --ok:#1a7f37; --warning:#bf8700; --critical:#cf222e; --nm:#6e7781; }
  body { font-family: system-ui, sans-serif; margin: 0; color: #1f2328; background: #f6f8fa; }
  header { background: #0d1117; color: #fff; padding: 2rem; }
  header h1 { margin: 0 0 .25rem; font-size: 1.25rem; }
  .domain { margin: 0; color: #9da7b3; }
  .global { font-size: 3rem; font-weight: 700; margin: .5rem 0; }
  .global span { font-size: 1rem; color: #9da7b3; }
  .meta { margin: 0; color: #9da7b3; font-size: .8rem; }
  .score-ok { color: var(--ok); } .score-warning { color: var(--warning); }
  .score-critical { color: var(--critical); }
  .pillars { display: flex; flex-wrap: wrap; gap: 1rem; padding: 1.5rem 2rem; }
  .pillar { flex: 1 1 8rem; background: #fff; border-radius: 8px; padding: 1rem;
            border-top: 4px solid var(--nm); box-shadow: 0 1px 3px rgba(0,0,0,.08); }
  .pillar.ok { border-top-color: var(--ok); } .pillar.warning { border-top-color: var(--warning); }
  .pillar.critical { border-top-color: var(--critical); }
  .pname { font-weight: 600; color: #57606a; } .pscore { font-size: 1.8rem; font-weight: 700; }
  .pmeta { font-size: .75rem; color: #6e7781; }
  section.criteria { padding: 0 2rem 1.5rem; }
  h2 { font-size: 1rem; border-bottom: 1px solid #d0d7de; padding-bottom: .25rem; }
  table { width: 100%; border-collapse: collapse; background: #fff; font-size: .82rem; }
  th, td { text-align: left; padding: .45rem .6rem; border-bottom: 1px solid #eaeef2;
           vertical-align: top; }
  th { background: #f6f8fa; color: #57606a; }
  td.num { text-align: right; font-variant-numeric: tabular-nums; }
  td.key, td.mono { font-family: ui-monospace, monospace; font-size: .76rem; color: #57606a; }
  .badge { display: inline-block; padding: .1rem .45rem; border-radius: 999px; color: #fff;
           font-size: .72rem; text-transform: uppercase; }
  .badge.ok { background: var(--ok); } .badge.warning { background: var(--warning); }
  .badge.critical { background: var(--critical); } .badge.nm { background: var(--nm); }
  footer { padding: 1.5rem 2rem; color: #6e7781; font-size: .8rem; }
</style>
</head>
<body>
<header>
  <h1>Audit Seryvon</h1>
  <p class="domain">{{ report.domain }}</p>
  <div class="global score-{{ global_css }}">
    {{ "%.1f"|format(report.score_global) }}<span>/100</span>
  </div>
  <p class="meta">
    Seryvon {{ report.tool_version }} · {{ generated }} · schéma v{{ report.schema_version }}
    · couverture {{ (report.coverage * 100)|round|int }}%
    {%- if report.config_digest %} · config {{ report.config_digest }}{% endif %}
  </p>
</header>
<section class="pillars">
  {% for p in pillars %}
  <div class="pillar {{ p.css }}">
    <div class="pname">{{ p.name }}</div>
    <div class="pscore">{% if p.measured %}{{ "%.1f"|format(p.score) }}{% else %}—{% endif %}</div>
    <div class="pmeta">{{ p.measured }} mesurés · {{ p.excluded }} exclus ·
      {{ (p.coverage * 100)|round|int }}% couv.</div>
  </div>
  {% endfor %}
</section>
{% if report.issues %}
<section class="criteria">
  <h2>Plan d'action — {{ report.issues|length }} problème(s)</h2>
  <table>
    <thead><tr>
      <th>Priorité</th><th>Critère</th><th>Sévérité</th>
      <th>Impact</th><th>Effort</th><th>Recommandation</th>
    </tr></thead>
    <tbody>
    {% for issue in report.issues %}
      <tr>
        <td>{{ issue.priority_bucket }}</td>
        <td class="key">{{ issue.criterion_key }}</td>
        <td><span class="badge {{ issue.severity }}">{{ issue.severity }}</span></td>
        <td class="num">{{ issue.impact }}</td>
        <td class="num">{{ issue.effort }}</td>
        <td>{{ issue.recommendation }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</section>
{% endif %}
{% for s in sections %}
<section class="criteria">
  <h2>{{ s.pillar }} — {{ s.rows|length }} critère(s)</h2>
  <table>
    <thead><tr>
      <th>Critère</th><th>Statut</th><th>Score</th><th>Poids</th>
      <th>Explication</th><th>Seuil</th><th>Valeur mesurée</th><th>Source</th>
    </tr></thead>
    <tbody>
    {% for r in s.rows %}
      <tr>
        <td class="key">{{ r.key }}</td>
        <td><span class="badge {{ r.status_css }}">{{ r.status }}</span></td>
        <td class="num">{{ "%.1f"|format(r.score) }}</td>
        <td class="num">{{ r.weight }}</td>
        <td>{{ r.explanation }}</td>
        <td class="mono">{{ r.threshold|tojson }}</td>
        <td class="mono">{{ r.raw_value|tojson }}</td>
        <td class="mono">{{ r.evidence|tojson }}</td>
      </tr>
    {% endfor %}
    </tbody>
  </table>
</section>
{% endfor %}
<footer>Généré par Seryvon — audit déterministe SEO · GEO · GSO · AEO · ASO.</footer>
</body>
</html>
"""


def report_to_html(report: AuditReport) -> str:
    """Render an audit report as a self-contained, deterministic HTML page."""
    pillars = [
        {
            "name": name.upper(),
            "score": ps.score,
            "measured": ps.measured,
            "excluded": ps.excluded,
            "coverage": ps.coverage,
            "css": _band(ps.score) if ps.measured else "nm",
        }
        for name, ps in report.pillars.items()
    ]
    sections: list[dict[str, Any]] = []
    for name in report.pillars:
        rows = [_row(c) for c in sorted(report.criteria, key=lambda c: c.key) if name in c.pillars]
        if rows:
            sections.append({"pillar": name.upper(), "rows": rows})

    moment: datetime = report.finished_at or report.started_at
    env = Environment(autoescape=True, trim_blocks=True, lstrip_blocks=True)
    template = env.from_string(_TEMPLATE)
    return template.render(
        report=report,
        pillars=pillars,
        sections=sections,
        global_css=_band(report.score_global),
        generated=moment.strftime("%Y-%m-%d %H:%M UTC"),
    )
