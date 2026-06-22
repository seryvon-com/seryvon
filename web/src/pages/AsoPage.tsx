// Seryvon — ASO Readiness page: agentic readiness band + ASO criteria. AGPL-3.0-or-later.

import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { AppShell } from "../components/AppShell";
import { AsoBand } from "../components/AsoBand";
import type { AuditReport, CriterionResult } from "../api/types";
import { useI18n } from "../i18n";

function AsoScore({ score, status }: { score: number; status: string }) {
  const cls =
    status === "ok" ? "ok" : status === "warning" ? "warning" : status === "critical" ? "critical" : "muted";
  return (
    <span className={`score-pill ${cls}`}>{Math.round(score)}</span>
  );
}

function AsoCriteriaTable({ criteria }: { criteria: CriterionResult[] }) {
  const { t } = useI18n();
  if (criteria.length === 0) return null;
  return (
    <div style={{ marginTop: 24 }}>
      <div className="section-header">
        <span className="kicker">{t.asoPage.criteriaTitle}</span>
      </div>
      <table className="data-table">
        <thead>
          <tr>
            <th>{t.criteria.colCriterion}</th>
            <th>{t.criteria.colScore}</th>
            <th>{t.criteria.explanation}</th>
          </tr>
        </thead>
        <tbody>
          {criteria.map((c) => (
            <tr key={c.key}>
              <td>
                <span style={{ fontFamily: "var(--font-mono)", fontSize: 11 }}>{c.key}</span>
                {t.ruleLabel[c.key] && (
                  <div style={{ fontSize: 12, color: "var(--c-text-muted)", marginTop: 2 }}>
                    {t.ruleLabel[c.key]}
                  </div>
                )}
              </td>
              <td>
                {c.status === "not_measured" || c.status === "not_applicable" ? (
                  <span style={{ fontSize: 11, color: "var(--c-text-faint)" }}>
                    {t.statusLabel[c.status]}
                  </span>
                ) : (
                  <AsoScore score={c.score} status={c.status} />
                )}
              </td>
              <td style={{ fontSize: 13, color: "var(--c-text-soft)" }}>
                {c.explanation || t.criteria.noExplanation}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

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
          setError(
            err instanceof ApiError ? t.report.notFound(err.status) : t.report.loadError,
          );
      });
    return () => {
      active = false;
    };
  }, [auditId, t]);

  const asoCriteria = report?.criteria.filter((c) => c.pillars.includes("aso")) ?? [];
  const asoScore = report?.pillars["aso"]?.score ?? null;

  return (
    <AppShell
      domain={report?.domain}
      lastAudit={report ? formatDate(report.started_at) : undefined}
      auditId={auditId}
      active="asoReadiness"
      title={t.asoPage.title}
      subtitle={t.asoPage.subtitle}
    >
      {error && <div className="notice error">{error}</div>}
      {!error && !report && <div className="notice">{t.report.loading}</div>}
      {report && report.aso_readiness && (
        <AsoBand readiness={report.aso_readiness} score={asoScore} />
      )}
      {report && <AsoCriteriaTable criteria={asoCriteria} />}
    </AppShell>
  );
}
