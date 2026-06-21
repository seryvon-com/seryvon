// Seryvon — visibility spectrum (per-pillar bars). AGPL-3.0-or-later.

import type { AuditReport } from "../api/types";
import { PILLARS, PILLAR_LABELS } from "../api/types";
import { pillarColor } from "../lib/format";

export function Spectrum({ report }: { report: AuditReport }) {
  return (
    <div className="card spectrum">
      <h3 style={{ marginBottom: 14 }}>Spectre de visibilité</h3>
      {PILLARS.map((p) => {
        const ps = report.pillars[p];
        if (!ps) return null;
        const color = pillarColor(p);
        return (
          <div className="row" key={p}>
            <div className="top">
              <span className="name">{PILLAR_LABELS[p]}</span>
              <span className="val" style={{ color }}>
                {ps.score.toFixed(0)}
              </span>
            </div>
            <div className="bar-track">
              <div className="bar-fill" style={{ width: `${ps.score}%`, background: color }} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
