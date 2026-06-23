// Seryvon — audit history page for a domain (PRISM). AGPL-3.0-or-later.

import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { AppShell } from "../components/AppShell";
import type { AuditReport, AuditSummary } from "../api/types";
import { useI18n } from "../i18n";

export function HistoryPage() {
  const { auditId } = useParams<{ auditId: string }>();
  const { t, formatDate } = useI18n();
  const navigate = useNavigate();
  const [report, setReport] = useState<AuditReport | null>(null);
  const [history, setHistory] = useState<AuditSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!auditId) return;
    let active = true;
    setReport(null);
    setHistory(null);
    setError(null);
    api
      .getAudit(auditId)
      .then((r) => {
        if (!active) return;
        setReport(r);
        return api.listAudits(r.domain).then((h) => {
          if (active) setHistory(h);
        });
      })
      .catch((err) => {
        if (active)
          setError(err instanceof ApiError ? t.report.notFound(err.status) : t.report.loadError);
      });
    return () => {
      active = false;
    };
  }, [auditId, t]);

  return (
    <AppShell
      domain={report?.domain}
      lastAudit={report ? formatDate(report.started_at) : undefined}
      auditId={auditId}
      active="history"
      title={t.history.title}
      subtitle={t.history.subtitle}
    >
      {error && <div className="notice error">{error}</div>}
      {!error && !history && <div className="notice">{t.report.loading}</div>}
      {history && history.length === 0 && <div className="notice">{t.history.empty}</div>}
      {history && history.length > 0 && (
        <div className="card">
          <div className="section-head">
            <h3>{t.history.title}</h3>
            <span className="section-sub">{t.history.count(history.length)}</span>
          </div>
          <table className="criteria-table">
            <thead>
              <tr>
                <th>{t.history.colDate}</th>
                <th style={{ textAlign: "right" }}>{t.history.colScore}</th>
                <th style={{ textAlign: "right" }}>{t.history.colMeasured}</th>
                <th>{t.history.colId}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {history.map((h) => (
                <tr key={h.audit_id}>
                  <td>{formatDate(h.started_at)}</td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>
                    {h.score_global == null ? "—" : Math.round(h.score_global)}
                  </td>
                  <td style={{ textAlign: "right", fontFamily: "var(--font-mono)", color: "var(--c-text-muted)" }}>
                    {h.criteria_measured > 0 ? h.criteria_measured : "—"}
                  </td>
                  <td style={{ fontFamily: "var(--font-mono)", fontSize: 11, color: "var(--c-text-faint)" }}>
                    {h.audit_id}
                  </td>
                  <td style={{ textAlign: "right" }}>
                    <button
                      className="btn"
                      type="button"
                      onClick={() => navigate(`/audits/${h.audit_id}`)}
                    >
                      {t.history.view}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </AppShell>
  );
}
