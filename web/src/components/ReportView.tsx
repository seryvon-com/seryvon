// Seryvon — full audit report view (PRISM dashboard). AGPL-3.0-or-later.

import type { AuditReport } from "../api/types";
import { PILLARS } from "../api/types";
import { formatDuration } from "../lib/format";
import { AsoBand } from "./AsoBand";
import { IssueList } from "./IssueList";
import { PillarCard } from "./PillarCard";
import { ScoreGauge } from "./ScoreGauge";
import { Spectrum } from "./Spectrum";

export function ReportView({ report }: { report: AuditReport }) {
  const applicable = report.criteria.filter((c) => c.status !== "not_applicable");
  const measured = applicable.filter(
    (c) => c.status !== "not_measured" && c.status !== "not_applicable",
  ).length;
  const notMeasured = applicable.length - measured;
  const aso = report.pillars["aso"];

  return (
    <>
      {/* Global score hero */}
      <div className="hero">
        <div className="mono-label">SCORE GLOBAL DE VISIBILITÉ</div>
        <div className="gauge-row">
          <ScoreGauge score={report.score_global} size={150} numSize={42} unit="/ 100" prism />
          <div className="summary">
            {measured} critères mesurés sur {applicable.length} · {notMeasured} marqués{" "}
            <code>not_measured</code>. Scoring déterministe, traçable jusqu'à la donnée source.
          </div>
        </div>
        <div className="stats">
          <div>
            <div className="val">{measured}</div>
            <div className="cap">CRITÈRES MESURÉS</div>
          </div>
          <div>
            <div className="val">{formatDuration(report.started_at, report.finished_at)}</div>
            <div className="cap">DURÉE</div>
          </div>
          <div>
            <div className="val">{report.issues.length}</div>
            <div className="cap">PROBLÈMES</div>
          </div>
          <div>
            <div className="val">{Math.round(report.coverage * 100)} %</div>
            <div className="cap">COUVERTURE</div>
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
            <h3>Problèmes prioritaires</h3>
          </div>
          <div className="section-sub">Priorité calculée : (impact × sévérité) / effort</div>
          <IssueList issues={report.issues.slice(0, 6)} />
        </div>
        <Spectrum report={report} />
      </div>
    </>
  );
}
