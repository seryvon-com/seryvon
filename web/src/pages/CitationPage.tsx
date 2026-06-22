// Seryvon — LLM citation tracking page (PRISM). AGPL-3.0-or-later.

import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";

import { api, ApiError } from "../api/client";
import type { CitationMetrics } from "../api/types";
import { AppShell } from "../components/AppShell";
import { useI18n } from "../i18n";

export function CitationPage() {
  const { auditId } = useParams<{ auditId: string }>();
  const { t } = useI18n();

  const [domain, setDomain] = useState("");
  const [brand, setBrand] = useState("");
  const [competitors, setCompetitors] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [metrics, setMetrics] = useState<CitationMetrics | null>(null);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Pre-fill domain from the current audit.
  useEffect(() => {
    if (!auditId) return;
    api.getAudit(auditId).then((r) => setDomain(r.domain)).catch(() => undefined);
  }, [auditId]);

  // Poll citation task.
  useEffect(() => {
    if (!taskId) return;
    intervalRef.current = setInterval(() => {
      api
        .getCitationTask(taskId)
        .then((status) => {
          if (status.status === "done" && status.metrics) {
            clearInterval(intervalRef.current!);
            intervalRef.current = null;
            setTaskId(null);
            setRunning(false);
            setMetrics(status.metrics);
          } else if (status.status === "failed") {
            clearInterval(intervalRef.current!);
            intervalRef.current = null;
            setTaskId(null);
            setRunning(false);
            setError(status.error ?? t.citationTrack.errorRun);
          }
        })
        .catch(() => {
          clearInterval(intervalRef.current!);
          intervalRef.current = null;
          setTaskId(null);
          setRunning(false);
          setError(t.report.loadError);
        });
    }, 2500);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [taskId, t]);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!domain.trim() || running) return;
    setRunning(true);
    setError(null);
    setMetrics(null);
    try {
      const comps = competitors
        .split(",")
        .map((s) => s.trim())
        .filter(Boolean);
      const task = await api.runCitations(domain.trim(), brand.trim() || undefined, comps);
      setTaskId(task.task_id);
    } catch (err) {
      setRunning(false);
      if (err instanceof ApiError && err.status === 422) {
        setError(t.citationTrack.noKeys);
      } else {
        setError(err instanceof ApiError ? err.message : t.citationTrack.errorRun);
      }
    }
  }

  const pct = (v: number) => `${Math.round(v * 100)} %`;

  return (
    <AppShell auditId={auditId} active="citation" title={t.citationTrack.title} subtitle={t.citationTrack.subtitle}>
      <form className="card" style={{ display: "flex", flexDirection: "column", gap: 14 }} onSubmit={onSubmit}>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <label className="field-group">
            <span className="field-label">{t.citationTrack.domainLabel}</span>
            <input
              className="compare-input"
              value={domain}
              onChange={(e) => setDomain(e.target.value)}
              placeholder="world-models.io"
              required
            />
          </label>
          <label className="field-group">
            <span className="field-label">{t.citationTrack.brandLabel}</span>
            <input
              className="compare-input"
              value={brand}
              onChange={(e) => setBrand(e.target.value)}
              placeholder={t.citationTrack.brandPlaceholder}
            />
          </label>
        </div>
        <label className="field-group">
          <span className="field-label">{t.citationTrack.competitorsLabel}</span>
          <input
            className="compare-input"
            value={competitors}
            onChange={(e) => setCompetitors(e.target.value)}
            placeholder={t.citationTrack.competitorsPlaceholder}
          />
        </label>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <button className="btn" type="submit" disabled={running || !domain.trim()}>
            {running ? t.citationTrack.running : t.citationTrack.run}
          </button>
          {running && (
            <div className="audit-progress" style={{ flex: 1, margin: 0 }} role="status">
              <div className="bar"><span className="fill" /></div>
            </div>
          )}
        </div>
        {error && <div className="notice error">{error}</div>}
      </form>

      {metrics && <CitationResults metrics={metrics} t={t} pct={pct} />}
    </AppShell>
  );
}

function CitationResults({
  metrics,
  t,
  pct,
}: {
  metrics: CitationMetrics;
  t: ReturnType<typeof useI18n>["t"];
  pct: (v: number) => string;
}) {
  const gauges = [
    { label: t.citationTrack.citationRate, value: metrics.citation_rate, accent: "var(--c-seo)" },
    { label: t.citationTrack.mentionRate, value: metrics.mention_rate, accent: "var(--c-geo)" },
    { label: t.citationTrack.confidence, value: metrics.citation_confidence, accent: "var(--c-gso)" },
  ];
  if (metrics.share_of_voice !== null) {
    gauges.push({ label: t.citationTrack.shareOfVoice, value: metrics.share_of_voice, accent: "var(--c-aeo)" });
  }

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 16, marginTop: 4 }}>
      {/* Summary gauges */}
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))", gap: 12 }}>
        {gauges.map(({ label, value, accent }) => (
          <div key={label} className="card" style={{ textAlign: "center", padding: "18px 12px" }}>
            <div style={{ fontSize: 28, fontFamily: "var(--font-mono)", fontWeight: 700, color: accent }}>
              {pct(value)}
            </div>
            <div style={{ fontSize: 11, color: "var(--c-text-3)", marginTop: 4, textTransform: "uppercase", letterSpacing: "0.06em" }}>
              {label}
            </div>
          </div>
        ))}
      </div>

      {/* Footer stats */}
      <div style={{ display: "flex", gap: 20, fontSize: 12, color: "var(--c-text-3)", fontFamily: "var(--font-mono)" }}>
        <span>{t.citationTrack.engines}: {metrics.engines.join(", ") || t.citationTrack.na}</span>
        <span>{t.citationTrack.prompts}: {metrics.prompt_count}</span>
        <span>{t.citationTrack.repetitions}: {metrics.repetitions}</span>
      </div>

      {/* Per-engine table */}
      {Object.keys(metrics.per_engine).length > 0 && (
        <div className="card" style={{ padding: 0, overflow: "hidden" }}>
          <div style={{ padding: "12px 16px 8px", fontSize: 11, fontWeight: 700, letterSpacing: "0.06em", color: "var(--c-text-2)", textTransform: "uppercase" }}>
            {t.citationTrack.perEngine}
          </div>
          <table className="criteria-table" style={{ width: "100%" }}>
            <thead>
              <tr>
                <th>{t.citationTrack.colEngine}</th>
                <th>{t.citationTrack.colCitationRate}</th>
                <th>{t.citationTrack.colMentionRate}</th>
                <th>{t.citationTrack.colAvgPos}</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(metrics.per_engine).map(([engine, m]) => (
                <tr key={engine}>
                  <td style={{ fontFamily: "var(--font-mono)", fontWeight: 600 }}>{engine}</td>
                  <td>{pct(m.citation_rate)}</td>
                  <td>{pct(m.mention_rate)}</td>
                  <td>{m.average_position !== null ? m.average_position.toFixed(1) : t.citationTrack.na}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
