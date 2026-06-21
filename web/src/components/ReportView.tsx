// Seryvon — full audit report view. AGPL-3.0-or-later.

import type { AuditReport } from "../api/types";
import { PILLARS } from "../api/types";
import { formatDate } from "../lib/format";
import { IssueList } from "./IssueList";
import { PillarCard } from "./PillarCard";
import { ScoreGauge } from "./ScoreGauge";

export function ReportView({ report }: { report: AuditReport }) {
  return (
    <>
      <div className="report-head">
        <ScoreGauge score={report.score_global} />
        <div>
          <h2 className="domain">{report.domain}</h2>
          <div className="meta">
            Audité le {formatDate(report.started_at)} · v{report.tool_version} · couverture{" "}
            {Math.round(report.coverage * 100)} %
          </div>
          {report.measurement_profile && (
            <div className="meta">
              Profil de mesure <code>{report.measurement_profile.digest}</code> ·{" "}
              {report.measurement_profile.active_connectors.join(", ")}
            </div>
          )}
        </div>
      </div>

      <div className="pillars">
        {PILLARS.map((p) => {
          const ps = report.pillars[p];
          return ps ? <PillarCard key={p} pillar={ps} /> : null;
        })}
      </div>

      <section className="section">
        <h2>Plan d'action priorisé</h2>
        <IssueList issues={report.issues} />
      </section>
    </>
  );
}
