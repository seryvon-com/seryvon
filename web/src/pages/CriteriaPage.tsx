// Seryvon — audit report page: detailed criteria table (PRISM). AGPL-3.0-or-later.

import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { AppShell } from "../components/AppShell";
import { CriteriaTable } from "../components/CriteriaTable";
import type { AuditReport } from "../api/types";
import { useI18n } from "../i18n";

export function CriteriaPage() {
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

  return (
    <AppShell
      domain={report?.domain}
      lastAudit={report ? formatDate(report.started_at) : undefined}
      auditId={auditId}
      active="report"
      title={t.criteria.title}
      subtitle={t.criteria.subtitle}
    >
      {error && <div className="notice error">{error}</div>}
      {!error && !report && <div className="notice">{t.report.loading}</div>}
      {report && <CriteriaTable report={report} />}
    </AppShell>
  );
}
