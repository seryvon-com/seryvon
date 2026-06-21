// Seryvon — non-text display helpers (colors, buckets). AGPL-3.0-or-later.
// All human-readable strings live in src/i18n.

import type { Pillar, ReadinessLevel, Status } from "../api/types";

const PILLAR_COLORS: Record<string, string> = {
  seo: "var(--c-pillar-seo)",
  geo: "var(--c-pillar-geo)",
  gso: "var(--c-pillar-gso)",
  aeo: "var(--c-pillar-aeo)",
  aso: "var(--c-pillar-aso)",
};

export function pillarColor(pillar: string): string {
  return PILLAR_COLORS[pillar] ?? "var(--accent)";
}

/** Health bucket of a [0-100] score, matching the backend status thresholds. */
export function scoreBucket(score: number): "ok" | "warning" | "critical" {
  if (score >= 80) return "ok";
  if (score >= 50) return "warning";
  return "critical";
}

export function scoreColor(score: number): string {
  return `var(--c-${scoreBucket(score)})`;
}

export function statusSeverity(status: Status): "critical" | "warning" {
  return status === "critical" ? "critical" : "warning";
}

/** ASO readiness band: how many of the 4 segments to light for a level. */
const READINESS_LADDER: ReadinessLevel[] = ["none", "basic", "ready", "advanced"];
export function readinessReached(level: ReadinessLevel): number {
  const idx = READINESS_LADDER.indexOf(level);
  return idx <= 0 ? (level === "none" ? 0 : 1) : idx + 1;
}

export function isPillar(key: string): key is Pillar {
  return ["seo", "geo", "gso", "aeo", "aso"].includes(key);
}

/** Split a duration into (seconds<60) or (minutes, remainder) for locale formatting. */
export function durationParts(
  startIso: string,
  endIso: string | null,
): { kind: "none" } | { kind: "s"; s: number } | { kind: "m"; m: number; s: number } {
  if (!endIso) return { kind: "none" };
  const ms = new Date(endIso).getTime() - new Date(startIso).getTime();
  if (!Number.isFinite(ms) || ms < 0) return { kind: "none" };
  const s = Math.round(ms / 1000);
  if (s < 60) return { kind: "s", s };
  return { kind: "m", m: Math.floor(s / 60), s: s % 60 };
}
