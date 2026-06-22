// Seryvon — Prompt Set page: citation measurement instrument (M4b, doc 08). AGPL-3.0-or-later.

import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import type { Prompt, PromptIntent, PromptSet } from "../api/types";
import { AppShell } from "../components/AppShell";
import { useI18n } from "../i18n";

const INTENT_COLOR: Record<PromptIntent, string> = {
  definitional: "#60a5fa",
  comparative: "#f472b6",
  recommendation: "#34d399",
  explanatory: "#a78bfa",
  listing: "#fbbf24",
  use_case: "#fb923c",
  news: "#94a3b8",
};

function IntentBadge({ intent, label }: { intent: PromptIntent; label: string }) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        borderRadius: 4,
        fontSize: "0.7rem",
        fontWeight: 600,
        letterSpacing: "0.04em",
        textTransform: "uppercase",
        background: `${INTENT_COLOR[intent]}22`,
        color: INTENT_COLOR[intent],
        border: `1px solid ${INTENT_COLOR[intent]}44`,
        whiteSpace: "nowrap",
      }}
    >
      {label}
    </span>
  );
}

function QualityBar({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
      <div
        style={{
          width: 56,
          height: 6,
          borderRadius: 3,
          background: "var(--surface-2, #1e2330)",
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${pct}%`,
            height: "100%",
            background: pct >= 75 ? "#34d399" : pct >= 55 ? "#fbbf24" : "#f87171",
            borderRadius: 3,
          }}
        />
      </div>
      <span style={{ fontSize: "0.75rem", color: "var(--text-2, #94a3b8)", minWidth: 28 }}>
        {pct}%
      </span>
    </div>
  );
}

function ThemeProfileCard({ ps }: { ps: PromptSet }) {
  const { t } = useI18n();
  const p = t.promptSetPage;
  const tp = ps.theme_profile;
  return (
    <div className="card" style={{ marginBottom: "1.5rem" }}>
      <div className="card-header" style={{ marginBottom: "1rem" }}>
        <span className="kicker">{p.themeProfile}</span>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(220px, 1fr))", gap: "1.25rem" }}>
        <div>
          <div className="stat-label" style={{ marginBottom: 4 }}>{p.brand}</div>
          <div style={{ fontWeight: 600 }}>{tp.brand ?? p.none}</div>
        </div>
        <div>
          <div className="stat-label" style={{ marginBottom: 4 }}>{p.contentType}</div>
          <div style={{ fontWeight: 600 }}>
            {p.contentTypes[tp.content_type] ?? tp.content_type}
          </div>
        </div>
        <div>
          <div className="stat-label" style={{ marginBottom: 4 }}>{p.topics}</div>
          {tp.topics.length > 0 ? (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {tp.topics.map((topic) => (
                <span
                  key={topic}
                  style={{
                    padding: "2px 8px",
                    borderRadius: 4,
                    background: "#1e2330",
                    border: "1px solid #2d3346",
                    fontSize: "0.75rem",
                  }}
                >
                  {topic}
                </span>
              ))}
            </div>
          ) : (
            <span style={{ color: "var(--text-2, #94a3b8)" }}>{p.none}</span>
          )}
        </div>
        <div>
          <div className="stat-label" style={{ marginBottom: 4 }}>{p.entities}</div>
          {tp.entities.length > 0 ? (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {tp.entities.map((entity) => (
                <span
                  key={entity}
                  style={{
                    padding: "2px 8px",
                    borderRadius: 4,
                    background: "#1e2330",
                    border: "1px solid #2d3346",
                    fontSize: "0.75rem",
                  }}
                >
                  {entity}
                </span>
              ))}
            </div>
          ) : (
            <span style={{ color: "var(--text-2, #94a3b8)" }}>{p.none}</span>
          )}
        </div>
      </div>
    </div>
  );
}

function PromptsTable({ prompts }: { prompts: Prompt[] }) {
  const { t } = useI18n();
  const p = t.promptSetPage;
  return (
    <table className="data-table">
      <thead>
        <tr>
          <th style={{ width: 140 }}>{p.colIntent}</th>
          <th>{p.colText}</th>
          <th style={{ width: 100 }}>{p.colQuality}</th>
        </tr>
      </thead>
      <tbody>
        {prompts.map((pr, i) => (
          <tr key={i}>
            <td>
              <IntentBadge intent={pr.intent} label={p.intents[pr.intent] ?? pr.intent} />
            </td>
            <td style={{ fontFamily: "var(--font-mono, monospace)", fontSize: "0.82rem" }}>
              {pr.text}
            </td>
            <td>
              <QualityBar score={pr.quality_score} />
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function PromptSetPage() {
  const { auditId } = useParams<{ auditId: string }>();
  const { t, formatDate } = useI18n();
  const [ps, setPs] = useState<PromptSet | null>(null);
  const [domain, setDomain] = useState<string | undefined>();
  const [lastAudit, setLastAudit] = useState<string | undefined>();
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!auditId) return;
    let active = true;
    setPs(null);
    setError(null);

    // Load audit metadata for the shell header
    api.getAudit(auditId).then((r) => {
      if (active) {
        setDomain(r.domain);
        setLastAudit(formatDate(r.started_at));
      }
    }).catch(() => {/* non-fatal */});

    api
      .getPromptSet(auditId)
      .then((data) => { if (active) setPs(data); })
      .catch((err) => {
        if (!active) return;
        if (err instanceof ApiError && err.status === 404) {
          setError(t.promptSetPage.noData);
        } else {
          setError(t.report.loadError);
        }
      });
    return () => { active = false; };
  }, [auditId, t, formatDate]);

  const p = t.promptSetPage;

  return (
    <AppShell
      domain={domain}
      lastAudit={lastAudit}
      auditId={auditId}
      active="promptSet"
      title={p.title}
      subtitle={p.subtitle}
    >
      {error && <div className="notice error">{error}</div>}
      {!error && !ps && <div className="notice">{t.report.loading}</div>}
      {ps && (
        <>
          <ThemeProfileCard ps={ps} />
          <div className="section-header" style={{ marginBottom: "0.75rem" }}>
            <span className="kicker">{p.prompts}</span>
            <span style={{ marginLeft: 8, color: "var(--text-2, #94a3b8)", fontSize: "0.8rem" }}>
              {p.promptCount(ps.prompts.length)}
            </span>
          </div>
          <PromptsTable prompts={ps.prompts} />
        </>
      )}
    </AppShell>
  );
}
