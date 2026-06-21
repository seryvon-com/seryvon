// Seryvon — report page: load a persisted audit by id (PRISM). AGPL-3.0-or-later.

import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { AppShell } from "../components/AppShell";
import { ReportView } from "../components/ReportView";
import type { AuditReport } from "../api/types";
import { formatDate } from "../lib/format";

export function ReportPage() {
  const { auditId } = useParams<{ auditId: string }>();
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
            err instanceof ApiError
              ? `Rapport introuvable (${err.status})`
              : "Échec du chargement — le backend est-il démarré ?",
          );
      });
    return () => {
      active = false;
    };
  }, [auditId]);

  return (
    <AppShell
      title="Vue d'ensemble"
      subtitle="Scorecard déterministe sur les cinq piliers"
      domain={report?.domain}
      lastAudit={report ? formatDate(report.started_at) : undefined}
    >
      {error && <div className="notice error">{error}</div>}
      {!error && !report && <div className="notice">Chargement du rapport…</div>}
      {report && <ReportView report={report} />}
    </AppShell>
  );
}
