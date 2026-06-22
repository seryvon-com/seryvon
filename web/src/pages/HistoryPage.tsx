// Seryvon — audit history page: all audits for a domain. AGPL-3.0-or-later.

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
        return api.listAudits(r.domain);
      })
      .then((list) => {
        if (active && list) setHistory(list);
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

  return (
    <AppShell
      domain={report?.domain}
      lastAudit={report ? formatDate(report.started_at) : undefined}
      auditId={auditId}
      active="history"
      title={t.history.title}
      subtitle={report ? t.history.subtitle(report.domain) : ""}
    >
      {error && <div className="notice error">{error}</div>}
      {!error && !history && <div className="notice">{t.report.loading}</div>}
      {history && history.length === 0 && (
        <div className="notice">{t.history.noHistory}</div>
      )}
      {history && history.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>{t.history.colDate}</th>
              <th>{t.history.colScore}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {history.map((entry) => (
              <tr key={entry.audit_id}>
                <td>{formatDate(entry.started_at)}</td>
                <td>
                  {entry.score_global != null ? (
                    <span className="score-pill">{Math.round(entry.score_global)}</span>
                  ) : (
                    <span style={{ color: "var(--c-text-faint)" }}>—</span>
                  )}
                </td>
                <td>
                  <button
                    className="btn-small"
                    onClick={() => navigate(`/audits/${entry.audit_id}`)}
                  >
                    {t.history.view}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </AppShell>
  );
}
