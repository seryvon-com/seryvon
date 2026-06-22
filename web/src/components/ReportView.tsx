// Seryvon — full audit report view (PRISM dashboard). AGPL-3.0-or-later.

import type { AuditReport } from "../api/types";
import { PILLARS } from "../api/types";
import { useI18n } from "../i18n";
import { durationParts } from "../lib/format";
import { AsoBand } from "./AsoBand";
import { IssueList } from "./IssueList";
import { PillarCard } from "./PillarCard";
import { ScoreGauge } from "./ScoreGauge";
import { Spectrum } from "./Spectrum";

export function ReportView({ report }: { report: AuditReport }) {
  const { t } = useI18n();
  const applicable = report.criteria.filter((c) => c.status !== "not_applicable");
  const measured = applicable.filter(
    (c) => c.status !== "not_measured" && c.status !== "not_applicable",
  ).length;
  const notMeasured = applicable.length - measured;
  const aso = report.pillars["aso"];

  const d = durationParts(report.started_at, report.finished_at);
  const duration =
    d.kind === "s" ? t.durationSeconds(d.s) : d.kind === "m" ? t.durationMinutes(d.m, d.s) : "—";

  return (
    <>
      {/* Global score hero */}
      <div className="hero">
        <div className="mono-label">{t.report.scoreGlobal}</div>
        <div className="gauge-row">
          <ScoreGauge score={report.score_global} size={150} numSize={42} unit="/ 100" prism />
          <div className="summary">
            {t.report.summary(measured, applicable.length, notMeasured)} <code>not_measured</code>.
          </div>
        </div>
        <div className="stats">
          <div>
            <div className="val">{measured}</div>
            <div className="cap">{t.report.statCriteria}</div>
          </div>
          <div>
            <div className="val">{duration}</div>
            <div className="cap">{t.report.statDuration}</div>
          </div>
          <div>
            <div className="val">{report.issues.length}</div>
            <div className="cap">{t.report.statIssues}</div>
          </div>
          <div>
            <div className="val">{Math.round(report.coverage * 100)} %</div>
            <div className="cap">{t.report.statCoverage}</div>
          </div>
        </div>
      </div>

      {/* Pillar gauge grid */}
      <div className="pillars">
        {PILLARS.map((p) => {
          const ps = report.pillars[p];
          return ps ? <PillarCard key={p} pillar={ps} /> : null;
        })}
      </div>

      {/* ASO readiness band */}
      {report.aso_readiness && (
        <AsoBand readiness={report.aso_readiness} score={aso ? aso.score : null} />
      )}

      {/* Lower row: issues + spectrum */}
      <div className="lower">
        <div className="card">
          <div className="section-head">
            <h3>{t.report.issuesTitle}</h3>
          </div>
          <div className="section-sub">{t.report.issuesSub}</div>
          <IssueList issues={report.issues.slice(0, 6)} />
        </div>
        <Spectrum report={report} />
      </div>
    </>
  );
}
