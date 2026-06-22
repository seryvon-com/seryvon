// Seryvon — circular score gauge (PRISM). AGPL-3.0-or-later.

import { useId } from "react";

import { scoreColor } from "../lib/format";

interface Props {
  score: number;
  size?: number;
  /** Solid stroke color; ignored when `prism` is set. */
  color?: string;
  /** Use the five-hue prism gradient (global score). */
  prism?: boolean;
  numSize?: number;
  unit?: string;
}

export function ScoreGauge({ score, size = 120, color, prism, numSize, unit }: Props) {
  // useId() embeds colons (":r0:"); strip them so url(#id) resolves in SVG.
  const gradId = `g${useId().replace(/:/g, "")}`;
  const vb = 200;
  const stroke = 15;
  const r = 84;
  const c = 2 * Math.PI * r;
  const clamped = Math.max(0, Math.min(100, score));
  const offset = c * (1 - clamped / 100);
  const ringColor = prism ? `url(#${gradId})` : (color ?? scoreColor(clamped));

  return (
    <div className="gauge" style={{ width: size, height: size }}>
      <svg width={size} height={size} viewBox={`0 0 ${vb} ${vb}`} aria-hidden="true">
        {prism && (
          <defs>
            <linearGradient id={gradId} x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stopColor="#5b8cff" />
              <stop offset="25%" stopColor="#a77bff" />
              <stop offset="50%" stopColor="#3fd6a8" />
              <stop offset="75%" stopColor="#f6b24b" />
              <stop offset="100%" stopColor="#ef72b0" />
            </linearGradient>
          </defs>
        )}
        <circle cx="100" cy="100" r={r} fill="none" stroke="#222836" strokeWidth={stroke} />
        <circle
          cx="100"
          cy="100"
          r={r}
          fill="none"
          stroke={ringColor}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="center">
        <div
          className="num"
          style={{ fontSize: numSize ?? size * 0.28, color: prism ? "#fff" : ringColor }}
        >
          {Math.round(clamped)}
        </div>
        {unit && <div className="unit">{unit}</div>}
      </div>
    </div>
  );
}
