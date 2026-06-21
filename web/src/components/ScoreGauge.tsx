// Seryvon — circular score gauge. AGPL-3.0-or-later.

import { scoreColor } from "../lib/format";

interface Props {
  score: number;
  size?: number;
}

export function ScoreGauge({ score, size = 120 }: Props) {
  const stroke = 10;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.max(0, Math.min(100, score));
  const offset = circumference * (1 - clamped / 100);
  const center = size / 2;

  return (
    <div className="gauge" style={{ width: size, height: size }}>
      <svg width={size} height={size} aria-hidden="true">
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke="var(--c-border)"
          strokeWidth={stroke}
        />
        <circle
          cx={center}
          cy={center}
          r={radius}
          fill="none"
          stroke={scoreColor(clamped)}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
        />
      </svg>
      <div className="value" style={{ position: "absolute", color: scoreColor(clamped) }}>
        {Math.round(clamped)}
      </div>
    </div>
  );
}
