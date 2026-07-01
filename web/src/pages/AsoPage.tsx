// Seryvon — ASO readiness detail page (PRISM). AGPL-3.0-or-later.

import { useEffect, useState, type ReactNode } from "react";
import { useParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { AppShell } from "../components/AppShell";
import { AsoBand } from "../components/AsoBand";
import { CriterionHint } from "../components/CriterionHint";
import type { AsoReadiness, AuditReport } from "../api/types";
import { useI18n } from "../i18n";

export function AsoPage() {
  const { auditId } = useParams<{ auditId: string }>();
  const { t, formatDate } = useI18n();
  const [report, setReport] = useState<AuditReport | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!auditId) return;
    let active = true;
    setReport(null);
    setError(null);
    api
      .getAudit(auditId)
      .then((r) => {
        if (active) setReport(r);
      })
      .catch((err) => {
        if (active)
          setError(err instanceof ApiError ? t.report.notFound(err.status) : t.report.loadError);
      });
    return () => {
      active = false;
    };
  }, [auditId, t]);

  const aso = report?.aso_readiness ?? null;
  const asoScore = report?.pillars["aso"]?.score ?? null;

  return (
    <AppShell
      domain={report?.domain}
      lastAudit={report ? formatDate(report.started_at) : undefined}
      auditId={auditId}
      active="aso"
      title={t.asoDetail.title}
      subtitle={t.asoDetail.subtitle}
    >
      {error && <div className="notice error">{error}</div>}
      {!error && !report && <div className="notice">{t.report.loading}</div>}
      {report && !aso && <div className="notice">{t.asoDetail.unavailable}</div>}
      {report && aso && (
        <>
          <AsoBand readiness={aso} score={asoScore} />
          <div className="card" style={{ marginTop: 18 }}>
            <table className="criteria-table">
              <tbody>
                <AgentReadyRow aso={aso} />
                <Row
                  label={t.asoDetail.aiDiscovery}
                  hint={<CriterionHint criterionKey="aso.ai_discovery" rawValue={null} />}
                  value={String(aso.ai_discovery_endpoints)}
                />
                <Row
                  label={t.asoDetail.nlweb}
                  hint={<CriterionHint criterionKey="aso.nlweb" rawValue={null} />}
                  value={aso.has_nlweb ? t.asoDetail.yes : t.asoDetail.no}
                />
                <Row
                  label={t.asoDetail.brandCoherence}
                  hint={<CriterionHint criterionKey="aso.brand_coherence" rawValue={null} />}
                  value={aso.brand_coherence_score == null ? t.asoDetail.none : `${Math.round(aso.brand_coherence_score)}/100`}
                />
                <Row
                  label={t.asoDetail.blockedBots}
                  hint={<CriterionHint criterionKey="aso.agent_access" rawValue={null} />}
                  value={aso.blocked_agent_bots.length ? aso.blocked_agent_bots.join(", ") : t.asoDetail.none}
                />
              </tbody>
            </table>
          </div>
        </>
      )}
    </AppShell>
  );
}

function AgentReadyRow({ aso }: { aso: AsoReadiness }) {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);

  const signals: { key: string; label: string; ok: boolean; hint: string }[] = [
    { key: "webmcp", label: t.asoDetail.webmcp, ok: aso.has_webmcp, hint: t.asoDetail.agentReadyWebmcpMissing },
    {
      key: "action_schema",
      label: t.asoDetail.actionSchema,
      ok: aso.has_action_schema,
      hint: t.asoDetail.agentReadyActionSchemaMissing,
    },
    {
      key: "forms",
      label: t.asoDetail.agentReadyForms,
      ok: aso.has_agent_forms,
      hint: t.asoDetail.agentReadyFormsMissing,
    },
    {
      key: "openapi",
      label: t.asoDetail.agentReadyOpenapi,
      ok: aso.has_openapi,
      hint: t.asoDetail.agentReadyOpenapiMissing,
    },
  ];

  return (
    <>
      <tr
        onClick={() => setOpen((o) => !o)}
        style={{ cursor: "pointer" }}
        aria-expanded={open}
      >
        <td style={{ color: "var(--c-text-muted)" }}>
          <span
            style={{
              display: "inline-block",
              marginRight: 8,
              fontSize: 10,
              transform: open ? "rotate(90deg)" : "rotate(0deg)",
              transition: "transform 0.15s",
            }}
          >
            &#9656;
          </span>
          {t.asoDetail.agentReady}
          <CriterionHint criterionKey="aso.agent_ready" rawValue={null} />
        </td>
        <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>
          {aso.agent_ready ? t.asoDetail.yes : t.asoDetail.no}
        </td>
      </tr>
      {open && (
        <tr>
          <td colSpan={2} style={{ padding: 0 }}>
            <div style={{ background: "var(--c-bg, #0f1116)", padding: "10px 0 12px 28px" }}>
              <p style={{ fontSize: 12, color: "var(--c-text-faint)", margin: "0 0 8px" }}>
                {t.asoDetail.agentReadyExplainer(aso.action_signals)}
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                {signals.map((s) => (
                  <div
                    key={s.key}
                    style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}
                  >
                    <span style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13 }}>
                      <span style={{ color: s.ok ? "var(--c-ok)" : "var(--c-error)" }}>{s.ok ? "✓" : "✗"}</span>
                      {s.label}
                    </span>
                    {!s.ok && (
                      <span style={{ fontSize: 11, color: "var(--c-text-faint)" }}>{s.hint}</span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          </td>
        </tr>
      )}
    </>
  );
}

function Row({ label, value, hint }: { label: string; value: string; hint?: ReactNode }) {
  return (
    <tr>
      <td style={{ color: "var(--c-text-muted)" }}>
        {label}
        {hint}
      </td>
      <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>{value}</td>
    </tr>
  );
}
