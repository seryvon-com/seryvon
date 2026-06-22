// Seryvon — Outil d'audit SEO / GEO / GSO / AEO / ASO
// Copyright (C) 2026 Powehi <contact@powehi.eu> — https://seryvon.com
// Licensed under the GNU AGPL-3.0-or-later. See <https://www.gnu.org/licenses/>.
//
// TypeScript mirror of the FastAPI/Pydantic response models (src/seryvon/models/
// report.py). Kept hand-written and minimal until an OpenAPI codegen step lands.

export type Pillar = "seo" | "geo" | "gso" | "aeo" | "aso";

export const PILLARS: Pillar[] = ["seo", "geo", "gso", "aeo", "aso"];

export const PILLAR_LABELS: Record<Pillar, string> = {
  seo: "SEO",
  geo: "GEO",
  gso: "GSO",
  aeo: "AEO",
  aso: "ASO",
};

export type Status =
  | "ok"
  | "warning"
  | "critical"
  | "not_measured"
  | "not_applicable";

export type CoverageLabel =
  | "complete"
  | "substantial"
  | "partial"
  | "insufficient";

export type Severity = "warning" | "critical";

export type ReadinessLevel = "none" | "basic" | "ready" | "advanced";

export interface PillarScore {
  pillar: string;
  score: number;
  measured: number;
  excluded: number;
  not_applicable: number;
  coverage: number;
  coverage_label: CoverageLabel;
}

export interface CriterionResult {
  key: string;
  pillars: string[];
  raw_value: unknown;
  score: number;
  status: Status;
  threshold: Record<string, unknown>;
  explanation: string;
  evidence: Record<string, unknown>;
  weight: number;
  evidence_tier: string;
}

export interface Issue {
  criterion_key: string;
  severity: Severity;
  impact: number;
  effort: number;
  priority_score: number;
  priority_bucket: string; // P1 / P2 / P3 / P4
  recommendation: string;
  affected_pages: string[];
}

export interface AsoReadiness {
  readiness_level: ReadinessLevel;
  agent_ready: boolean;
  has_webmcp: boolean;
  has_action_schema: boolean;
  ai_discovery_endpoints: number;
  has_nlweb: boolean;
  brand_coherence_score: number | null;
  blocked_agent_bots: string[];
}

export interface MeasurementProfile {
  seryvon_version: string;
  signal_schema_version: number;
  rule_catalog_digest: string;
  pillar_weights: Record<string, number>;
  thresholds: Record<string, Record<string, unknown>>;
  criteria_overrides: Record<string, Record<string, unknown>>;
  active_connectors: string[];
  digest: string;
}

export interface ArtifactRef {
  project_id: string;
  run_id: string;
  type: string;
  bucket: string;
  object_key: string;
  sha256: string;
  mime_type: string;
  size_bytes: number;
  compression: string;
  encryption: boolean;
  retention_until: string | null;
  created_at: string | null;
}

export interface AuditReport {
  domain: string;
  tool_version: string;
  schema_version: number;
  started_at: string;
  finished_at: string | null;
  score_global: number;
  coverage: number;
  pillars: Record<string, PillarScore>;
  criteria: CriterionResult[];
  issues: Issue[];
  aso_readiness: AsoReadiness | null;
  config_digest: string | null;
  measurement_profile: MeasurementProfile | null;
  artifacts: ArtifactRef[];
}

export interface AuditSummary {
  audit_id: string;
  domain: string;
  score_global: number | null;
  started_at: string;
}
