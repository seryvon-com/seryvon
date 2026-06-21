// Seryvon — per-pillar summary card. AGPL-3.0-or-later.

import type { PillarScore } from "../api/types";
import { PILLAR_LABELS } from "../api/types";
import { COVERAGE_LABELS, isPillar, pillarColor, scoreColor } from "../lib/format";

export function PillarCard({ pillar }: { pillar: PillarScore }) {
  const label = isPillar(pillar.pillar) ? PILLAR_LABELS[pillar.pillar] : pillar.pillar.toUpperCase();
  return (
    <div className="pillar-card" style={{ ["--accent" as string]: pillarColor(pillar.pillar) }}>
      <div className="name">{label}</div>
      <div className="score" style={{ color: scoreColor(pillar.score) }}>
        {pillar.score.toFixed(0)}
      </div>
      <div className="coverage">
        {pillar.measured} mesuré{pillar.measured > 1 ? "s" : ""} ·{" "}
        {COVERAGE_LABELS[pillar.coverage_label]}
      </div>
    </div>
  );
}
