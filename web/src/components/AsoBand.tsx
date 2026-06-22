// Seryvon — ASO agentic-readiness band (the differentiator). AGPL-3.0-or-later.

import type { AsoReadiness } from "../api/types";
import { useI18n } from "../i18n";
import { readinessReached } from "../lib/format";

export function AsoBand({ readiness, score }: { readiness: AsoReadiness; score: number | null }) {
  const { t } = useI18n();
  const lit = readinessReached(readiness.readiness_level);
  const detail = readiness.has_webmcp
    ? t.aso.webmcpPresent
    : t.aso.webmcpAbsent(readiness.ai_discovery_endpoints);
  return (
    <div className="aso-band">
      <div style={{ display: "flex", alignItems: "center", gap: 13, flex: "0 0 auto" }}>
        <span className="dot" />
        <div>
          <div className="kicker">{t.aso.kicker}</div>
          <div className="level">
            {t.readiness[readiness.readiness_level]}
            {score != null && (
              <span style={{ fontSize: 13, fontWeight: 400, color: "var(--c-text-soft)" }}>
                {" "}
                {t.aso.score(Math.round(score))}
              </span>
            )}
          </div>
        </div>
      </div>
      <div className="steps">
        {[0, 1, 2, 3].map((i) => (
          <span key={i} className={`step${i < lit ? " on" : ""}`} />
        ))}
      </div>
      <div className="blurb">
        {t.aso.blurbLead}
        <b>{t.aso.blurbStrong}</b> — {detail}.
      </div>
    </div>
  );
}
