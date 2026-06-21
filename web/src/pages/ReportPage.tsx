// Seryvon — report page: load a persisted audit by id. AGPL-3.0-or-later.

import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { ReportView } from "../components/ReportView";
import { TopBar } from "../components/TopBar";
import type { AuditReport } from "../api/types";

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
      .then((r) => active && setReport(r))
      .catch((err) =>
        active &&
        setError(
          err instanceof ApiError
            ? `Rapport introuvable (${err.status})`
            : "Échec du chargement — le backend est-il démarré ?",
        ),
      );
    return () => {
      active = false;
    };
  }, [auditId]);

  return (
    <div className="app">
      <TopBar />
      {error && <div className="notice error">{error}</div>}
      {!error && !report && <div className="notice">Chargement du rapport…</div>}
      {report && <ReportView report={report} />}
    </div>
  );
}
