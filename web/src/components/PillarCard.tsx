// Seryvon — per-pillar gauge card (PRISM). AGPL-3.0-or-later.

import type { PillarScore } from "../api/types";
import { PILLAR_LABELS } from "../api/types";
import { useI18n } from "../i18n";
import { isPillar, pillarColor } from "../lib/format";

export function PillarCard({ pillar }: { pillar: PillarScore }) {
  const { t } = useI18n();
  const key = pillar.pillar;
  const isP = isPillar(key);
  const label = isP ? PILLAR_LABELS[key] : key.toUpperCase();
  const full = isP ? t.pillarFull[key] : "";
  const color = pillarColor(key);
  const coveragePct = Math.round(pillar.coverage * 100);
  const isPartial = pillar.coverage < 0.999;

  return (
    <div className="pillar-card">
      <div className="accent-bar" style={{ background: color }} />
      <div className="body">
        <GaugeMini score={pillar.score} coverage={pillar.coverage} color={color} />
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="name" style={{ color }}>
            {label}
          </div>
          <div className="full">{full}</div>
          <div className="pillar-coverage-row" style={{ marginTop: 8 }}>
            <span
              className={`pillar-coverage-label${isPartial ? " partial" : ""}`}
              title={t.coverage[pillar.coverage_label]}
            >
              {t.coverage[pillar.coverage_label]}
            </span>
            {isPartial && (
              <span className="pillar-coverage-pct">{coveragePct}%</span>
            )}
          </div>
        </div>
      </div>
      <div className="meta">
        <span>
          {pillar.measured} {t.pillar.measured}
        </span>
        <span className="sep">·</span>
        <span style={{ color: "var(--c-text-faint-2)" }}>
          {pillar.excluded} {t.pillar.excluded}
        </span>
      </div>
    </div>
  );
}

function GaugeMini({ score, coverage, color }: { score: number; coverage: number; color: string }) {
  const cx = 70, cy = 70;
  const r = 50;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, score));
  const scoreOffset = c * (1 - clamped / 100);
  const coverageClamped = Math.max(0, Math.min(1, coverage));
  const isPartial = coverage < 0.999;
  // Outer thin ring at a larger radius — stays visible regardless of score value.
  const r_cov = 63;
  const c_cov = 2 * Math.PI * r_cov;
  const covOffset = c_cov * (1 - coverageClamped);

  return (
    <div className="gauge" style={{ width: 70, height: 70, flex: "0 0 70px" }}>
      <svg width={70} height={70} viewBox="0 0 140 140" aria-hidden="true">
        {/* main donut track */}
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="#222836" strokeWidth={11} />
        {/* score arc */}
        <circle
          cx={cx} cy={cy} r={r}
          fill="none" stroke={color} strokeWidth={11} strokeLinecap="round"
          strokeDasharray={c} strokeDashoffset={scoreOffset}
          style={{ transform: "rotate(-90deg)", transformOrigin: `${cx}px ${cy}px` }}
        />
        {/* outer coverage ring — dark track (unmeasured) + colored arc (measured) */}
        {isPartial && (
          <>
            <circle cx={cx} cy={cy} r={r_cov} fill="none" stroke="#2a3050" strokeWidth={4} />
            <circle
              cx={cx} cy={cy} r={r_cov}
              fill="none" stroke={color} strokeWidth={4} strokeLinecap="round"
              strokeOpacity={0.75}
              strokeDasharray={c_cov} strokeDashoffset={covOffset}
              style={{ transform: "rotate(-90deg)", transformOrigin: `${cx}px ${cy}px` }}
            />
          </>
        )}
      </svg>
      <div className="center">
        <div className="num" style={{ fontSize: 18 }}>
          {Math.round(clamped)}
        </div>
      </div>
    </div>
  );
}
