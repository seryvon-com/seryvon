// Seryvon — ASO readiness detail page (PRISM). AGPL-3.0-or-later.

import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { AppShell } from "../components/AppShell";
import { AsoBand } from "../components/AsoBand";
import type { AuditReport } from "../api/types";
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
                <Row label={t.asoDetail.agentReady} value={aso.agent_ready ? t.asoDetail.yes : t.asoDetail.no} />
                <Row label={t.asoDetail.webmcp} value={aso.has_webmcp ? t.asoDetail.yes : t.asoDetail.no} />
                <Row
                  label={t.asoDetail.actionSchema}
                  value={aso.has_action_schema ? t.asoDetail.yes : t.asoDetail.no}
                />
                <Row label={t.asoDetail.aiDiscovery} value={String(aso.ai_discovery_endpoints)} />
                <Row label={t.asoDetail.nlweb} value={aso.has_nlweb ? t.asoDetail.yes : t.asoDetail.no} />
                <Row
                  label={t.asoDetail.brandCoherence}
                  value={aso.brand_coherence_score == null ? t.asoDetail.none : `${Math.round(aso.brand_coherence_score)}/100`}
                />
                <Row
                  label={t.asoDetail.blockedBots}
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

function Row({ label, value }: { label: string; value: string }) {
  return (
    <tr>
      <td style={{ color: "var(--c-text-muted)" }}>{label}</td>
      <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>{value}</td>
    </tr>
  );
}
