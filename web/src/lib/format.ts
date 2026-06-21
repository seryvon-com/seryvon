// Seryvon — display helpers. AGPL-3.0-or-later.

import type { CoverageLabel, Pillar, Status } from "../api/types";

const PILLAR_COLORS: Record<string, string> = {
  seo: "var(--c-pillar-seo)",
  geo: "var(--c-pillar-geo)",
  gso: "var(--c-pillar-gso)",
  aeo: "var(--c-pillar-aeo)",
  aso: "var(--c-pillar-aso)",
};

export function pillarColor(pillar: string): string {
  return PILLAR_COLORS[pillar] ?? "var(--c-accent)";
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

export function statusBadgeClass(status: Status): string {
  switch (status) {
    case "ok":
      return "ok";
    case "warning":
      return "warning";
    case "critical":
      return "critical";
    default:
      return "muted";
  }
}

export const COVERAGE_LABELS: Record<CoverageLabel, string> = {
  complete: "couverture complète",
  substantial: "couverture substantielle",
  partial: "couverture partielle",
  insufficient: "couverture insuffisante",
};

export function isPillar(key: string): key is Pillar {
  return ["seo", "geo", "gso", "aeo", "aso"].includes(key);
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toLocaleString("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}
