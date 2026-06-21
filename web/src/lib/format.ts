// Seryvon — display helpers. AGPL-3.0-or-later.

import type { CoverageLabel, Pillar, ReadinessLevel, Status } from "../api/types";

const PILLAR_COLORS: Record<string, string> = {
  seo: "var(--c-pillar-seo)",
  geo: "var(--c-pillar-geo)",
  gso: "var(--c-pillar-gso)",
  aeo: "var(--c-pillar-aeo)",
  aso: "var(--c-pillar-aso)",
};

/** Full pillar name shown under the acronym (PRISM mockup). */
export const PILLAR_FULL: Record<Pillar, string> = {
  seo: "Search Engine Optimization",
  geo: "Generative Engine Optimization",
  gso: "Generative Search Optimization",
  aeo: "Answer Engine Optimization",
  aso: "Agentic Search Optimization",
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

export const COVERAGE_LABELS: Record<CoverageLabel, string> = {
  complete: "couverture complète",
  substantial: "couverture substantielle",
  partial: "couverture partielle",
  insufficient: "couverture insuffisante",
};

/** Ordered ASO readiness ladder (PRISM band). */
export const READINESS_LADDER: ReadinessLevel[] = ["none", "basic", "ready", "advanced"];

export function readinessReached(level: ReadinessLevel): number {
  // none = 0 steps lit, basic = 1, ready = 2, advanced = 3 (band shows 4 segments;
  // "none" lights none, each tier above lights one more up to all four).
  const idx = READINESS_LADDER.indexOf(level);
  return idx <= 0 ? (level === "none" ? 0 : 1) : idx + 1;
}

export function isPillar(key: string): key is Pillar {
  return ["seo", "geo", "gso", "aeo", "aso"].includes(key);
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" });
}

export function formatDuration(startIso: string, endIso: string | null): string {
  if (!endIso) return "—";
  const ms = new Date(endIso).getTime() - new Date(startIso).getTime();
  if (!Number.isFinite(ms) || ms < 0) return "—";
  const s = Math.round(ms / 1000);
  if (s < 60) return `${s} s`;
  return `${Math.floor(s / 60)} m ${String(s % 60).padStart(2, "0")} s`;
}
