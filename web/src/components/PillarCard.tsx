// Seryvon — per-pillar gauge card (PRISM). AGPL-3.0-or-later.

import type { PillarScore } from "../api/types";
import { PILLAR_LABELS } from "../api/types";
import { COVERAGE_LABELS, PILLAR_FULL, isPillar, pillarColor } from "../lib/format";

export function PillarCard({ pillar }: { pillar: PillarScore }) {
  const key = pillar.pillar;
  const isP = isPillar(key);
  const label = isP ? PILLAR_LABELS[key] : key.toUpperCase();
  const full = isP ? PILLAR_FULL[key] : "";
  const color = pillarColor(key);

  return (
    <div className="pillar-card">
      <div className="accent-bar" style={{ background: color }} />
      <div className="body">
        <GaugeMini score={pillar.score} color={color} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="name" style={{ color }}>
            {label}
          </div>
          <div className="full">{full}</div>
          <div style={{ fontSize: 11, color: "var(--c-text-faint)", marginTop: 8 }}>
            {COVERAGE_LABELS[pillar.coverage_label]}
          </div>
        </div>
      </div>
      <div className="meta">
        <span>{pillar.measured} mesurés</span>
        <span className="sep">·</span>
        <span style={{ color: "var(--c-text-faint-2)" }}>{pillar.excluded} exclus</span>
      </div>
    </div>
  );
}

function GaugeMini({ score, color }: { score: number; color: string }) {
  const r = 50;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, score));
  const offset = c * (1 - clamped / 100);
  return (
    <div className="gauge" style={{ width: 62, height: 62, flex: "0 0 62px" }}>
      <svg width={62} height={62} viewBox="0 0 120 120" aria-hidden="true">
        <circle cx="60" cy="60" r={r} fill="none" stroke="#222836" strokeWidth={11} />
        <circle
          cx="60"
          cy="60"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth={11}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="center">
        <div className="num" style={{ fontSize: 18 }}>
          {Math.round(clamped)}
        </div>
      </div>
    </div>
  );
}
