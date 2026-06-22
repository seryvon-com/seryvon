// Seryvon — scorecard comparison page (PRISM). AGPL-3.0-or-later.

import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import type {
  AuditReport,
  AuditSummary,
  ComparisonResult,
} from "../api/types";
import { PILLAR_LABELS, PILLARS } from "../api/types";
import { AppShell } from "../components/AppShell";
import { useI18n } from "../i18n";
import type { Dict } from "../i18n/dict";
import { pillarColor } from "../lib/format";

export function ComparePage() {
  const { auditId } = useParams<{ auditId: string }>();
  const { t, formatDate } = useI18n();

  const [leftReport, setLeftReport] = useState<AuditReport | null>(null);
  const [leftError, setLeftError] = useState<string | null>(null);

  const [rightDomain, setRightDomain] = useState("");
  const [rightHistory, setRightHistory] = useState<AuditSummary[] | null>(null);
  const [rightHistoryLoading, setRightHistoryLoading] = useState(false);
  const [selectedRightId, setSelectedRightId] = useState<string | null>(null);

  const [result, setResult] = useState<ComparisonResult | null>(null);
  const [comparing, setComparing] = useState(false);
  const [compareError, setCompareError] = useState<string | null>(null);

  useEffect(() => {
    if (!auditId) return;
    let active = true;
    setLeftReport(null);
    setLeftError(null);
    api
      .getAudit(auditId)
      .then((r) => {
        if (!active) return;
        setLeftReport(r);
        setRightDomain(r.domain);
        setRightHistoryLoading(true);
        return api.listAudits(r.domain).then((h) => {
          if (!active) return;
          const others = h.filter((s) => s.audit_id !== auditId);
          setRightHistory(others);
          if (others.length > 0) setSelectedRightId(others[0].audit_id);
          setRightHistoryLoading(false);
        });
      })
      .catch((err) => {
        if (active)
          setLeftError(
            err instanceof ApiError ? t.report.notFound(err.status) : t.report.loadError,
          );
      });
    return () => {
      active = false;
    };
  }, [auditId, t]);

  function loadHistory() {
    const domain = rightDomain.trim();
    if (!domain) return;
    setRightHistoryLoading(true);
    setRightHistory(null);
    setSelectedRightId(null);
    setResult(null);
    setCompareError(null);
    api
      .listAudits(domain)
      .then((h) => {
        const others = h.filter((s) => s.audit_id !== auditId);
        setRightHistory(others);
        if (others.length > 0) setSelectedRightId(others[0].audit_id);
        setRightHistoryLoading(false);
      })
      .catch(() => {
        setRightHistory([]);
        setRightHistoryLoading(false);
      });
  }

  function runCompare() {
    if (!auditId || !selectedRightId) return;
    setComparing(true);
    setResult(null);
    setCompareError(null);
    api
      .compareAudits(auditId, selectedRightId, "descriptive")
      .then((r) => {
        setResult(r);
        setComparing(false);
      })
      .catch((err) => {
        setCompareError(
          err instanceof ApiError
            ? `${err.status}: ${err.message}`
            : t.compare.errorCompare,
        );
        setComparing(false);
      });
  }

  const selectedRight =
    rightHistory?.find((s) => s.audit_id === selectedRightId) ?? null;

  return (
    <AppShell
      domain={leftReport?.domain}
      lastAudit={leftReport ? formatDate(leftReport.started_at) : undefined}
      auditId={auditId}
      active="compare"
      title={t.compare.title}
      subtitle={t.compare.subtitle}
    >
      {leftError && <div className="notice error">{leftError}</div>}
      {!leftError && !leftReport && <div className="notice">{t.report.loading}</div>}
      {leftReport && (
        <>
          <div className="compare-grid">
            {/* Left — reference */}
            <div className="card">
              <div className="mono-label" style={{ marginBottom: 10 }}>
                {t.compare.leftAudit}
              </div>
              <div style={{ fontFamily: "var(--font-mono)", fontSize: 14, color: "var(--c-text)" }}>
                {leftReport.domain}
              </div>
              <div style={{ fontSize: 11.5, color: "var(--c-text-faint)", marginTop: 3 }}>
                {formatDate(leftReport.started_at)}
              </div>
              <div
                style={{
                  fontFamily: "var(--font-display)",
                  fontWeight: 700,
                  fontSize: 32,
                  marginTop: 14,
                  lineHeight: 1,
                }}
              >
                {Math.round(leftReport.score_global)}
                <span style={{ fontSize: 13, color: "var(--c-text-faint)", marginLeft: 5 }}>
                  /100
                </span>
              </div>
            </div>

            {/* Right — comparison target */}
            <div className="card">
              <div className="mono-label" style={{ marginBottom: 10 }}>
                {t.compare.rightAudit}
              </div>
              <div style={{ display: "flex", gap: 8, marginBottom: 14 }}>
                <input
                  className="compare-input"
                  type="text"
                  value={rightDomain}
                  onChange={(e) => setRightDomain(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && loadHistory()}
                  placeholder={t.compare.domainPlaceholder}
                />
                <button className="btn" onClick={loadHistory} disabled={rightHistoryLoading}>
                  {rightHistoryLoading ? t.compare.loadingHistory : t.compare.loadHistory}
                </button>
              </div>

              {rightHistory !== null && rightHistory.length === 0 && (
                <div style={{ fontSize: 12, color: "var(--c-text-faint)" }}>
                  {t.compare.noHistory(rightDomain)}
                </div>
              )}

              {rightHistory && rightHistory.length > 0 && (
                <div className="compare-run-list">
                  {rightHistory.slice(0, 8).map((h) => (
                    <button
                      key={h.audit_id}
                      type="button"
                      className={`compare-run-item${selectedRightId === h.audit_id ? " selected" : ""}`}
                      onClick={() => {
                        setSelectedRightId(h.audit_id);
                        setResult(null);
                      }}
                    >
                      <span style={{ fontSize: 12, color: "var(--c-text-muted)" }}>
                        {formatDate(h.started_at)}
                      </span>
                      <span
                        style={{
                          fontFamily: "var(--font-mono)",
                          fontWeight: 600,
                          marginLeft: "auto",
                          color: "var(--c-text)",
                        }}
                      >
                        {h.score_global == null ? "—" : Math.round(h.score_global)}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div style={{ display: "flex", justifyContent: "flex-end", margin: "16px 0" }}>
            <button
              className="btn"
              onClick={runCompare}
              disabled={!selectedRightId || comparing}
            >
              {comparing ? "…" : t.compare.compareBtn}
            </button>
          </div>

          {compareError && <div className="notice error">{compareError}</div>}

          {result && (
            <ComparisonView
              result={result}
              leftReport={leftReport}
              rightSummary={selectedRight}
              t={t}
              formatDate={formatDate}
            />
          )}
        </>
      )}
    </AppShell>
  );
}

function ComparisonView({
  result,
  leftReport,
  rightSummary,
  t,
  formatDate,
}: {
  result: ComparisonResult;
  leftReport: AuditReport;
  rightSummary: AuditSummary | null;
  t: Dict;
  formatDate: (iso: string) => string;
}) {
  const [onlyChanged, setOnlyChanged] = useState(false);
  const delta = result.global_delta;

  const deltaColor =
    delta == null
      ? "var(--c-text-faint)"
      : delta > 0
        ? "var(--c-ok)"
        : delta < 0
          ? "var(--c-critical)"
          : "var(--c-text-muted)";

  const fmt = (n: number | null) => (n == null ? "—" : String(Math.round(n)));
  const fmtDelta = (d: number | null) =>
    d == null ? "—" : (d >= 0 ? "+" : "") + Math.round(d);

  return (
    <>
      {/* Global summary card */}
      <div className="card" style={{ marginBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16, flexWrap: "wrap" }}>
          {/* Left score */}
          <div>
            <div style={{ fontSize: 11.5, color: "var(--c-text-faint)", fontFamily: "var(--font-mono)" }}>
              {leftReport.domain} · {formatDate(leftReport.started_at)}
            </div>
            <div
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 700,
                fontSize: 38,
                lineHeight: 1,
                marginTop: 6,
              }}
            >
              {fmt(result.left_global)}
            </div>
          </div>

          {/* Delta + comparability */}
          <div style={{ flex: 1, textAlign: "center", minWidth: 90 }}>
            <div
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 700,
                fontSize: 28,
                color: deltaColor,
              }}
            >
              {fmtDelta(delta)}
            </div>
            <div className="mono-label" style={{ marginTop: 4 }}>
              {t.compare.globalDelta}
            </div>
            <div
              className={`compare-badge compare-badge-${result.comparability}`}
              style={{ marginTop: 8, display: "inline-block" }}
            >
              {t.compare.comparability[result.comparability]}
            </div>
          </div>

          {/* Right score */}
          <div style={{ textAlign: "right" }}>
            {rightSummary && (
              <div style={{ fontSize: 11.5, color: "var(--c-text-faint)", fontFamily: "var(--font-mono)" }}>
                {rightSummary.domain} · {formatDate(rightSummary.started_at)}
              </div>
            )}
            <div
              style={{
                fontFamily: "var(--font-display)",
                fontWeight: 700,
                fontSize: 38,
                lineHeight: 1,
                marginTop: 6,
              }}
            >
              {fmt(result.right_global)}
            </div>
          </div>
        </div>

        {result.recomputed && (
          <div style={{ marginTop: 12, fontSize: 12, color: "var(--c-text-faint)" }}>
            * {t.compare.recomputed}
          </div>
        )}
        {result.profile_differences.length > 0 && (
          <div style={{ marginTop: 6, fontSize: 12, color: "var(--c-text-faint)" }}>
            {t.compare.profileDiffs(result.profile_differences.length)}:{" "}
            <span style={{ fontFamily: "var(--font-mono)" }}>
              {result.profile_differences.join(", ")}
            </span>
          </div>
        )}
      </div>

      {/* Pillar deltas */}
      {result.pillars.length > 0 && (
        <div className="pillars" style={{ marginBottom: 16 }}>
          {PILLARS.map((pillar) => {
            const pd = result.pillars.find((p) => p.pillar === pillar);
            if (!pd) return null;
            const d = pd.delta;
            const dColor =
              d == null
                ? "var(--c-text-faint)"
                : d > 0
                  ? "var(--c-ok)"
                  : d < 0
                    ? "var(--c-critical)"
                    : "var(--c-text-muted)";
            return (
              <div key={pillar} className="pillar-card">
                <div className="accent-bar" style={{ background: pillarColor(pillar) }} />
                <div className="body">
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div className="name" style={{ color: pillarColor(pillar) }}>
                      {PILLAR_LABELS[pillar]}
                    </div>
                    <div
                      style={{
                        display: "flex",
                        gap: 8,
                        alignItems: "baseline",
                        marginTop: 10,
                        fontFamily: "var(--font-mono)",
                        fontSize: 13,
                      }}
                    >
                      <span style={{ color: "var(--c-text-muted)" }}>{fmt(pd.left_score)}</span>
                      <span style={{ color: dColor, fontWeight: 700, fontSize: 15 }}>
                        {fmtDelta(d)}
                      </span>
                      <span style={{ color: "var(--c-text-muted)" }}>{fmt(pd.right_score)}</span>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Criteria delta table */}
      {result.criteria.length > 0 && (
        <div className="card">
          <div className="section-head" style={{ marginBottom: 14 }}>
            <h3>{t.compare.colDelta}</h3>
            <label
              style={{
                display: "flex",
                alignItems: "center",
                gap: 7,
                fontSize: 12,
                color: "var(--c-text-faint)",
                cursor: "pointer",
              }}
            >
              <input
                type="checkbox"
                checked={onlyChanged}
                onChange={(e) => setOnlyChanged(e.target.checked)}
              />
              {t.compare.onlyChanges}
            </label>
          </div>
          <table className="criteria-table">
            <thead>
              <tr>
                <th>{t.criteria.colCriterion}</th>
                <th style={{ textAlign: "right" }}>{t.compare.colLeft}</th>
                <th style={{ textAlign: "right" }}>{t.compare.colDelta}</th>
                <th style={{ textAlign: "right" }}>{t.compare.colRight}</th>
              </tr>
            </thead>
            <tbody>
              {result.criteria
                .filter((c) => !onlyChanged || (c.delta != null && c.delta !== 0))
                .sort((a, b) => Math.abs(b.delta ?? 0) - Math.abs(a.delta ?? 0))
                .map((c) => {
                  const d = c.delta;
                  const dColor =
                    d == null
                      ? "var(--c-text-faint)"
                      : d > 0
                        ? "var(--c-ok)"
                        : d < 0
                          ? "var(--c-critical)"
                          : "var(--c-text-muted)";
                  return (
                    <tr key={c.key}>
                      <td
                        style={{
                          fontFamily: "var(--font-mono)",
                          fontSize: 11,
                          color: "var(--c-text-faint)",
                        }}
                      >
                        {c.key}
                      </td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>
                        {fmt(c.left_score)}
                      </td>
                      <td
                        style={{
                          textAlign: "right",
                          fontFamily: "var(--font-mono)",
                          color: dColor,
                          fontWeight: d != null && d !== 0 ? 600 : undefined,
                        }}
                      >
                        {fmtDelta(d)}
                      </td>
                      <td style={{ textAlign: "right", fontFamily: "var(--font-mono)" }}>
                        {fmt(c.right_score)}
                      </td>
                    </tr>
                  );
                })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
