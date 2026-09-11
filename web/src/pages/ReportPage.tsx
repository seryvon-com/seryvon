// Seryvon — report page: load a persisted audit by id (PRISM). AGPL-3.0-or-later.

import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { AppShell } from "../components/AppShell";
import { CrawledPages } from "../components/CrawledPages";
import { ReportView } from "../components/ReportView";
import type { AuditReport } from "../api/types";
import { useI18n } from "../i18n";

function DownloadPdfButton({
  auditId,
  domain,
  label,
  locale,
}: {
  auditId: string;
  domain: string;
  label: string;
  locale: string;
}) {
  const [busy, setBusy] = useState(false);

  function handleClick() {
    setBusy(true);
    const anchor = document.createElement("a");
    anchor.href = `/api/audits/${auditId}/report.pdf?locale=${locale}`;
    anchor.download = `seryvon-${domain}.pdf`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => setBusy(false), 500);
  }

  return (
    <>
      <button className="btn btn-ghost btn-sm" onClick={handleClick} disabled={busy}>
        {busy ? "…" : `↓ ${label}`}
      </button>
    </>
  );
}

export function ReportPage() {
  const { auditId } = useParams<{ auditId: string }>();
  const { t, locale, formatDate } = useI18n();
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
        if (active) setError(err instanceof ApiError ? t.report.notFound(err.status) : t.report.loadError);
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
      active="overview"
    >
      {error && <div className="notice error">{error}</div>}
      {!error && !report && <div className="notice">{t.report.loading}</div>}
      {report && (
        <>
          <div className="report-toolbar">
            <DownloadPdfButton auditId={auditId!} domain={report.domain} label={t.report.downloadPdf} locale={locale} />
          </div>
          <ReportView report={report} />
          <CrawledPages auditId={auditId!} />
        </>
      )}
    </AppShell>
  );
}
