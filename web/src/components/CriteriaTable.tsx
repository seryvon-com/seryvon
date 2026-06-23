// Seryvon — detailed criteria table (PRISM). AGPL-3.0-or-later.
//
// Lists every scored CriterionResult, grouped by primary pillar, with a pillar
// filter and status toggles. Each row expands to show the traceability fields
// (raw_value, threshold, explanation, evidence). Labels are localized client-side
// (t.ruleLabel); the explanation is the text baked into the report at audit time.

import { useMemo, useState } from "react";

import type { AuditReport, CriterionResult, Pillar, Status } from "../api/types";
import { PILLARS, PILLAR_LABELS } from "../api/types";
import { useI18n } from "../i18n";
import { isPillar, pillarColor, scoreBucket } from "../lib/format";

const STATUSES: Status[] = ["ok", "warning", "critical", "not_measured", "not_applicable"];

/** Compact one-line rendering of an arbitrary JSON value for the inline detail. */
function formatValue(value: unknown, none: string): string {
  if (value === null || value === undefined || value === "") return none;
  if (Array.isArray(value)) {
    return value.length ? value.map((v) => formatValue(v, none)).join(", ") : none;
  }
  if (typeof value === "object") return JSON.stringify(value);
  if (typeof value === "number") return String(Math.round(value * 1000) / 1000);
  return String(value);
}

function primaryPillar(c: CriterionResult): string {
  return c.pillars[0] ?? "seo";
}

export function CriteriaTable({ report }: { report: AuditReport }) {
  const { t } = useI18n();
  const [pillarFilter, setPillarFilter] = useState<Pillar | "all">("all");
  const [hidden, setHidden] = useState<Set<Status>>(() => new Set());
  const [expanded, setExpanded] = useState<Set<string>>(
    () => new Set(report.criteria.filter((c) => c.status === "not_measured").map((c) => c.key)),
  );

  const filtered = useMemo(() => {
    return report.criteria.filter((c) => {
      if (hidden.has(c.status)) return false;
      if (pillarFilter !== "all" && !c.pillars.includes(pillarFilter)) return false;
      return true;
    });
  }, [report.criteria, pillarFilter, hidden]);

  // When showing all pillars, group under section headers in canonical order;
  // otherwise a single flat group keyed by the active pillar.
  const groups = useMemo(() => {
    if (pillarFilter !== "all") {
      return [{ pillar: pillarFilter as string, items: filtered }];
    }
    return PILLARS.map((p) => ({
      pillar: p as string,
      items: filtered.filter((c) => primaryPillar(c) === p),
    })).filter((g) => g.items.length > 0);
  }, [filtered, pillarFilter]);

  function toggleStatus(s: Status) {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(s)) next.delete(s);
      else next.add(s);
      return next;
    });
  }

  function toggleRow(key: string) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  return (
    <div className="criteria">
      <div className="criteria-toolbar">
        <div className="filter-chips">
          <button
            type="button"
            className={`chip ${pillarFilter === "all" ? "on" : ""}`}
            onClick={() => setPillarFilter("all")}
          >
            {t.criteria.filterAll}
          </button>
          {PILLARS.map((p) => (
            <button
              key={p}
              type="button"
              className={`chip ${pillarFilter === p ? "on" : ""}`}
              style={pillarFilter === p ? { borderColor: pillarColor(p), color: pillarColor(p) } : undefined}
              onClick={() => setPillarFilter(p)}
            >
              {PILLAR_LABELS[p]}
            </button>
          ))}
        </div>
        <div className="filter-chips status">
          {STATUSES.map((s) => (
            <button
              key={s}
              type="button"
              className={`chip dot-${s} ${hidden.has(s) ? "off" : "on"}`}
              onClick={() => toggleStatus(s)}
            >
              <span className="dot" />
              {t.statusLabel[s]}
            </button>
          ))}
        </div>
      </div>

      {groups.length === 0 ? (
        <div className="notice">{t.criteria.empty}</div>
      ) : (
        groups.map((g) => {
          const color = isPillar(g.pillar) ? pillarColor(g.pillar) : "var(--accent)";
          const label = isPillar(g.pillar) ? PILLAR_LABELS[g.pillar] : g.pillar.toUpperCase();
          return (
            <div className="criteria-group" key={g.pillar}>
              <div className="group-head">
                <span className="bar" style={{ background: color }} />
                <span className="name" style={{ color }}>
                  {label}
                </span>
                <span className="count">{t.criteria.count(g.items.length)}</span>
              </div>
              <div className="rows">
                {g.items.map((c) => (
                  <CriterionRow
                    key={c.key}
                    criterion={c}
                    open={expanded.has(c.key)}
                    onToggle={() => toggleRow(c.key)}
                  />
                ))}
              </div>
            </div>
          );
        })
      )}
    </div>
  );
}

function CriterionRow({
  criterion: c,
  open,
  onToggle,
}: {
  criterion: CriterionResult;
  open: boolean;
  onToggle: () => void;
}) {
  const { t } = useI18n();
  const label = t.ruleLabel[c.key] ?? c.key;
  const scored = c.status !== "not_measured" && c.status !== "not_applicable";
  const bucket = scored ? scoreBucket(c.score) : null;
  const thresholdEntries = Object.entries(c.threshold ?? {});
  const evidenceEntries = Object.entries(c.evidence ?? {});

  return (
    <div className={`crit-row ${open ? "open" : ""}`}>
      <button type="button" className="crit-summary" onClick={onToggle} aria-expanded={open}>
        <span className="caret" aria-hidden="true">
          ▸
        </span>
        <span className={`status-badge ${c.status}`}>{t.statusLabel[c.status]}</span>
        <span className="crit-main">
          <span className="crit-label">
            {label}
            {c.evidence_tier === "experimental" && (
              <span className="tier-badge">{t.criteria.tierExperimental}</span>
            )}
          </span>
          <span className="crit-key">{c.key}</span>
        </span>
        <span className="crit-pillars">
          {c.pillars.map((p) => (
            <span
              key={p}
              className="pillar-tag"
              style={{ color: isPillar(p) ? pillarColor(p) : undefined }}
            >
              {isPillar(p) ? PILLAR_LABELS[p] : p.toUpperCase()}
            </span>
          ))}
        </span>
        <span className="crit-score">
          {scored ? (
            <span className={`score-val ${bucket}`}>{Math.round(c.score)}</span>
          ) : (
            <span className="score-val muted">{t.criteria.none}</span>
          )}
          <span className="weight">×{c.weight}</span>
        </span>
      </button>

      {open && (
        <div className="crit-detail">
          <dl>
            <dt>{t.criteria.explanation}</dt>
            <dd>{c.explanation || t.criteria.noExplanation}</dd>

            <dt>{t.criteria.rawValue}</dt>
            <dd className="mono">{formatValue(c.raw_value, t.criteria.none)}</dd>

            {thresholdEntries.length > 0 && (
              <>
                <dt>{t.criteria.threshold}</dt>
                <dd className="mono">
                  {thresholdEntries.map(([k, v]) => (
                    <span className="kv" key={k}>
                      {k}: {formatValue(v, t.criteria.none)}
                    </span>
                  ))}
                </dd>
              </>
            )}

            {evidenceEntries.length > 0 && (
              <>
                <dt>{t.criteria.evidence}</dt>
                <dd className="mono">
                  {evidenceEntries.map(([k, v]) => (
                    <span className="kv" key={k}>
                      {k}: {formatValue(v, t.criteria.none)}
                    </span>
                  ))}
                </dd>
              </>
            )}
          </dl>
        </div>
      )}
    </div>
  );
}
