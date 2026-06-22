// Seryvon — Rank Tracking page: GSC keyword positions (M10). AGPL-3.0-or-later.

import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import { AppShell } from "../components/AppShell";
import type { AuditReport, GscQuery, GscResult } from "../api/types";
import { useI18n } from "../i18n";

function extractGscData(report: AuditReport): GscResult | null {
  const criterion = report.criteria.find((c) => c.key === "seo.avg_position");
  if (!criterion || !criterion.raw_value) return null;
  const rv = criterion.raw_value as Record<string, unknown>;
  if (rv.avg_position === null || rv.avg_position === undefined) return null;
  return {
    queries: (rv.queries as GscQuery[] | undefined) ?? [],
    total_clicks: (rv.total_clicks as number) ?? 0,
    total_impressions: (rv.total_impressions as number) ?? 0,
    avg_ctr: (rv.avg_ctr as number) ?? 0,
    avg_position: rv.avg_position as number,
    date_range_days: (rv.date_range_days as number) ?? 90,
  };
}

function StatCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="stat-card">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function RankTrackingView({ gsc }: { gsc: GscResult }) {
  const { t } = useI18n();
  const rt = t.rankTracking;
  const ctrPct = (gsc.avg_ctr * 100).toFixed(1);

  return (
    <div className="rank-tracking">
      <div className="section-header">
        <span className="kicker">{rt.dateRange(gsc.date_range_days)}</span>
      </div>

      <div className="stat-row">
        <StatCard
          label={rt.avgPosition}
          value={gsc.avg_position !== null ? String(gsc.avg_position) : "—"}
        />
        <StatCard label={rt.ctr} value={`${ctrPct}%`} />
        <StatCard label={rt.clicks} value={gsc.total_clicks.toLocaleString()} />
        <StatCard label={rt.impressions} value={gsc.total_impressions.toLocaleString()} />
      </div>

      {gsc.queries.length > 0 && (
        <table className="data-table">
          <thead>
            <tr>
              <th>{rt.table.keyword}</th>
              <th>{rt.table.position}</th>
              <th>{rt.table.clicks}</th>
              <th>{rt.table.impressions}</th>
              <th>{rt.table.ctr}</th>
            </tr>
          </thead>
          <tbody>
            {gsc.queries.map((q) => (
              <tr key={q.query}>
                <td>{q.query}</td>
                <td>{q.position.toFixed(1)}</td>
                <td>{q.clicks.toLocaleString()}</td>
                <td>{q.impressions.toLocaleString()}</td>
                <td>{(q.ctr * 100).toFixed(1)}%</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export function RankTrackingPage() {
  const { auditId } = useParams<{ auditId: string }>();
  const { t, formatDate } = useI18n();
  const navigate = useNavigate();
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

  const gsc = report ? extractGscData(report) : null;

  return (
    <AppShell
      domain={report?.domain}
      lastAudit={report ? formatDate(report.started_at) : undefined}
      auditId={auditId}
      active="rankTracking"
      title={t.rankTracking.title}
      subtitle={t.rankTracking.subtitle}
    >
      {error && <div className="notice error">{error}</div>}
      {!error && !report && <div className="notice">{t.report.loading}</div>}
      {report && !gsc && (
        <div className="notice">
          <p>{t.rankTracking.noData}</p>
          <p>{t.rankTracking.noKey}</p>
          <button className="btn" onClick={() => navigate("/")}>
            {t.topbar.runAudit}
          </button>
        </div>
      )}
      {report && gsc && <RankTrackingView gsc={gsc} />}
    </AppShell>
  );
}
