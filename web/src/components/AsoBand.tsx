// Seryvon — ASO agentic-readiness band (the differentiator). AGPL-3.0-or-later.

import type { AsoReadiness } from "../api/types";
import { readinessReached } from "../lib/format";

export function AsoBand({ readiness, score }: { readiness: AsoReadiness; score: number | null }) {
  const lit = readinessReached(readiness.readiness_level);
  const detail = readiness.has_webmcp
    ? "WebMCP présent"
    : `WebMCP absent · ${readiness.ai_discovery_endpoints} endpoint(s) de découverte IA`;
  return (
    <div className="aso-band">
      <div style={{ display: "flex", alignItems: "center", gap: 13, flex: "0 0 auto" }}>
        <span className="dot" />
        <div>
          <div className="kicker">READINESS AGENTIQUE · ASO</div>
          <div className="level">
            {readiness.readiness_level}
            {score != null && (
              <span style={{ fontSize: 13, fontWeight: 400, color: "var(--c-text-soft)" }}>
                {" "}
                · score {score.toFixed(0)}/100
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
        Le pilier que <b>personne d'autre n'audite</b> — {detail}.
      </div>
    </div>
  );
}
